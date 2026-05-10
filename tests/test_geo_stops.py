from unittest import TestCase

from app.geo_stops import COORDINATE_OVERRIDES, haversine_km, lat_lng_for_stop


class GeoStopsTests(TestCase):
    def test_haversine_zero(self) -> None:
        self.assertAlmostEqual(haversine_km(57.62, 39.87, 57.62, 39.87), 0.0, places=5)

    def test_haversine_order_of_km(self) -> None:
        d = haversine_km(57.62, 39.87, 57.70, 39.87)
        self.assertGreater(d, 5)
        self.assertLess(d, 20)

    def test_lat_lng_deterministic(self) -> None:
        a = lat_lng_for_stop("Ярославль", "Кировский район", "Центр", "Площадь Труда")
        b = lat_lng_for_stop("Ярославль", "Кировский район", "Центр", "Площадь Труда")
        self.assertEqual(a, b)

    def test_coordinate_overrides_used(self) -> None:
        ak = lat_lng_for_stop("Ярославль", "Фрунзенский район", "Сокол / Сокол-2", "ТЦ «Аксон»")
        self.assertEqual(ak, COORDINATE_OVERRIDES[
            ("Ярославль", "Фрунзенский район", "Сокол / Сокол-2", "ТЦ «Аксон»")
        ])

    def test_coordinate_overrides_cover_catalog_keys(self) -> None:
        self.assertGreaterEqual(len(COORDINATE_OVERRIDES), 30)

    def test_ul_bogdanovich6_akson_straight_line_farther_than_tolbukhina(self) -> None:
        """Ориентир: ул. Богдановича, 6 — Аксон по карте заметно южнее; расстояние по дуге должно быть больше."""
        user = (57.6297, 39.8617)
        tol = lat_lng_for_stop("Ярославль", "Кировский район", "Центр", "Проспект Толбухина")
        aks = lat_lng_for_stop("Ярославль", "Фрунзенский район", "Сокол / Сокол-2", "ТЦ «Аксон»")
        d_tol = haversine_km(user[0], user[1], tol[0], tol[1])
        d_aks = haversine_km(user[0], user[1], aks[0], aks[1])
        self.assertGreater(d_aks, d_tol + 2.0)

    def test_ul_belinskogo_farther_than_tolbukhina_near_bogdanovich(self) -> None:
        """Ул. Белинского в каталоге — севернее центра; от точки у Толбухина не должна быть ближе Толбухина."""
        user = (57.6297, 39.8617)
        tol = lat_lng_for_stop("Ярославль", "Кировский район", "Центр", "Проспект Толбухина")
        bel = lat_lng_for_stop("Ярославль", "Ленинский район", "Весь Ленинский район", "Улица Белинского")
        d_tol = haversine_km(user[0], user[1], tol[0], tol[1])
        d_bel = haversine_km(user[0], user[1], bel[0], bel[1])
        self.assertGreater(d_bel, d_tol + 1.0)

    def test_sokol_chernoprud_mayorova_south_of_center_vs_tolbukhina(self) -> None:
        """Сокол и НПЗ — заметно южнее центра; не должны считаться «рядом» с ул. Богдановича как при jitter."""
        user = (57.6297, 39.8617)
        tol = lat_lng_for_stop("Ярославль", "Кировский район", "Центр", "Проспект Толбухина")
        ch = lat_lng_for_stop("Ярославль", "Фрунзенский район", "Сокол / Сокол-2", "Улица Чернопрудная")
        mj = lat_lng_for_stop("Ярославль", "Красноперекопский район", "Новые Полянки", "Улица Майорова")
        d_tol = haversine_km(user[0], user[1], tol[0], tol[1])
        d_ch = haversine_km(user[0], user[1], ch[0], ch[1])
        d_mj = haversine_km(user[0], user[1], mj[0], mj[1])
        self.assertGreater(d_ch, d_tol + 3.0)
        self.assertGreater(d_mj, d_tol + 3.0)
