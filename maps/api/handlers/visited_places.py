from http import HTTPStatus
from typing import Tuple, Optional, Union

from aiohttp.web_response import json_response

from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200, r201, r400, r401
from pydantic import (
    confloat
)
from sqlalchemy import select, join, func, and_, between
from sqlalchemy.dialects.postgresql import insert

from maps.api import DEFAULT_PLACES
from maps.api.handlers.base import BaseView
from maps.api.schema import (
    ErrorResponseSchema,
    GetVisitedPlacesResponse,
    PostVisitedPlacesRequest, PostVisitedPlacesResponse,
    ScreenResolution, UserContext, PlaceState
)
from maps.db.schema import (
    users_table as user_t,
    places_table as places_t,
    user_places_table as user_places_t,
    user_feedbacks_table as user_feedbacks_t
)
from maps.utils.emulator_specifications import (
    EMULATOR_SCREEN, get_screen_coordinate_bounds,
)


class UserVisitedPlaces(PydanticView, BaseView):
    URL_PATH = '/visited_places'

    SRID = 4326
    WKT_POINT_TEMPLATE = 'POINT({} {})'
    state_kw = 'state'

    async def get(
        self,
        user_email: Optional[str] = 'maps@.y.r',
        latitude: confloat(ge=-90, le=90) = 1,
        longitude: confloat(ge=-180, le=180) = 1,
        zoom: confloat(ge=2, le=21) = 2,
        device_width: Optional[Union[int, float]] = EMULATOR_SCREEN.width,
        device_height: Optional[Union[int, float]] = EMULATOR_SCREEN.height,
        user_context: Optional[UserContext] = UserContext.ugc,
        *, token: Optional[str] = '',
    ) -> Union[r200[GetVisitedPlacesResponse]]:

        user_email = await self.get_email(user_email, token)

        # Returns value
        places = []

        if not await self.is_email_exists(user_email):
            # ТЕСТОВАЯ ФУНКЦИОНАЛЬНОСТЬ
            # Если юзера нет в базе, то добавляем для
            # него заранее определенные места
            # UPD: точки добавляются в файле миграции, поэтому
            # остается только замапить точки на юзера
            async with self.pg.begin() as conn:
                await conn.execute(insert(user_t).values(user_email=user_email))

                await conn.execute(
                    insert(user_places_t),
                    [
                        {"user_email": user_email, "place_uid": p_uid}
                        for p_uid, *_ in DEFAULT_PLACES
                    ]
                )

        device = ScreenResolution(device_width, device_height)
        point = self.WKT_POINT_TEMPLATE.format(longitude, latitude)

        # lb, up == lower and upper bounds
        lat_ub, lon_lb, lat_lb, lon_ub = (
            get_screen_coordinate_bounds(device, latitude, longitude, zoom)
        )

        places_wo_feedback_stmt = (
            select(user_feedbacks_t.c.place_uid)
            .select_from(user_feedbacks_t)
            .where(user_feedbacks_t.c.user_email == user_email)
        )

        places_stmt = (
            select(user_places_t.c.place_uid)
            .select_from(
                join(
                    user_places_t, places_wo_feedback_stmt,
                    user_places_t.c.place_uid == places_wo_feedback_stmt.c.place_uid,
                    isouter=True
                )
            )
            .where(
                and_(
                    places_wo_feedback_stmt.c.place_uid.is_(None),
                    user_places_t.c.user_email == user_email
                )
            )
        )

        stmt = (
            # Запрос возвращает посещенные места у которых нет
            # отзыва от текущего пользователя и которые находятся
            # в пределах вьюпорта девайса пользователя
            select([
                places_t.c.place_uid,
                places_t.c.place_id,
                func.ST_X(places_t.c.coordinates).label('longitude'),
                func.ST_Y(places_t.c.coordinates).label('latitude')
            ])
            .select_from(
                join(
                    places_t, places_stmt,
                    places_t.c.place_uid == places_stmt.c.place_uid,
                )
            )
            .where(
                and_(
                    between(func.ST_X(places_t.c.coordinates), lon_lb, lon_ub),
                    between(func.ST_Y(places_t.c.coordinates), lat_lb, lat_ub),
                )
            )
            .order_by(
                func.ST_Distance(
                    func.ST_GeomFromText(point, self.SRID),
                    places_t.c.coordinates
                )
            )
        )

        if user_context == UserContext.default:
            async with self.pg.connect() as conn:
                res = await conn.execute(stmt)

            # Берем первый элемент, т.к. запрос к БД
            # вернул отсортированный по дистанции список
            # mappings() возврает dict, вместо дефолтных туплов
            if place := res.mappings().first():
                places = [{**place, 'state': PlaceState.card}]

        else:
            async with self.pg.connect() as conn:
                res = await conn.execute(stmt)

            places = [
                {**place, 'state': PlaceState.plain_point}
                for place in res.mappings().all()
            ]

            # Изменяем PlaceState точек по критериям:
            # каждая четвертая - state=3, каждая третья - state=4, остальные - state=5.
            i = 1
            for place in places:
                if i % 3 == 0:
                    place['state'] = PlaceState.ico_wo_txt
                if i % 4 == 0:
                    place['state'] = PlaceState.ico_w_txt
                i += 1

            # Изменяем PlaceState на icon with text для первой(ближайшей) точки
            if places:
                places[0]['state'] = PlaceState.ico_w_txt

        return json_response({"places": places}, status=HTTPStatus.OK)

    async def post(
        self, place: PostVisitedPlacesRequest,
        *, token: Optional[str] = '',
    ) -> Union[r201[PostVisitedPlacesResponse]]:

        user_email = place.user_email
        place_uid = place.place_uid
        place_id = place.place_id
        coordinates = f'POINT({place.longitude} {place.latitude})'

        user_email = await self.get_email(user_email, token)

        async with self.pg.begin() as conn:
            # Если email пользователя не найден,
            # добавляем новую запись в таблицу users
            stmt = (
                insert(user_t)
                .values(user_email=user_email)
                .on_conflict_do_nothing()
            )
            await conn.execute(stmt)

            stmt = (
                insert(places_t)
                .values(
                    place_uid=place_uid,
                    place_id=place_id,
                    coordinates=coordinates
                )
                .on_conflict_do_nothing()
            )
            await conn.execute(stmt)

            stmt = (
                insert(user_places_t)
                .values(
                    user_email=user_email,
                    place_uid=place_uid
                )
                .returning(user_places_t.c.place_uid)
                .on_conflict_do_update(
                    index_elements=['user_email', 'place_uid'],
                    set_=dict(user_email=user_email, place_uid=place_uid),
                )
            )
            place_uid = await conn.execute(stmt)

        return json_response(
            {"place_uid": place_uid.scalar()},
            status=HTTPStatus.CREATED
        )
