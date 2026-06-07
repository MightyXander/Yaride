import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useUser } from "./state/UserContext";
import { LoadingView, ErrorView } from "./components/States";
import { NameInput } from "./screens/onboarding/NameInput";
import { RoleSelection } from "./screens/onboarding/RoleSelection";
import { DriverLicense } from "./screens/onboarding/DriverLicense";
import { Dashboard } from "./screens/Dashboard";
import { SelectDistrict } from "./screens/route/SelectDistrict";
import { SelectStop } from "./screens/route/SelectStop";
import { SearchResults } from "./screens/search/SearchResults";
import { RideDetails } from "./screens/search/RideDetails";
import { BookingConfirmation } from "./screens/search/BookingConfirmation";
import { CreateStart } from "./screens/create/CreateStart";
import { PublishFromTemplate } from "./screens/create/PublishFromTemplate";
import { DateTimeStep } from "./screens/create/DateTimeStep";
import { SeatsPriceStep } from "./screens/create/SeatsPriceStep";
import { ReviewPublish } from "./screens/create/ReviewPublish";
import { MyBookings } from "./screens/booking/MyBookings";
import { CancelBooking } from "./screens/booking/CancelBooking";
import { MyRides } from "./screens/manage/MyRides";
import { RatingThreshold } from "./screens/manage/RatingThreshold";
import { ManageBookings } from "./screens/manage/ManageBookings";
import { Account } from "./screens/account/Account";

export default function App() {
  const { me, loading, error, refresh } = useUser();
  const location = useLocation();
  const onOnboarding = location.pathname.startsWith("/onboarding");

  if (loading) return <LoadingView />;
  if (error) return <ErrorView message={error} onRetry={() => void refresh()} />;

  // Незарегистрированного пользователя ведём в онбординг (кроме самих экранов онбординга).
  if (me && !me.registered && !onOnboarding) {
    return <Navigate to="/onboarding/name" replace />;
  }

  return (
    <Routes>
      <Route path="/onboarding/name" element={<NameInput />} />
      <Route path="/onboarding/role" element={<RoleSelection />} />
      <Route path="/onboarding/license" element={<DriverLicense />} />

      <Route path="/" element={<Dashboard />} />

      <Route path="/route/district" element={<SelectDistrict />} />
      <Route path="/route/stop" element={<SelectStop />} />

      <Route path="/search/results" element={<SearchResults />} />
      <Route path="/ride/:id" element={<RideDetails />} />
      <Route path="/booking/confirm" element={<BookingConfirmation />} />

      <Route path="/create" element={<CreateStart />} />
      <Route path="/create/publish" element={<PublishFromTemplate />} />
      <Route path="/create/date-time" element={<DateTimeStep />} />
      <Route path="/create/seats-price" element={<SeatsPriceStep />} />
      <Route path="/create/review" element={<ReviewPublish />} />

      <Route path="/bookings" element={<MyBookings />} />
      <Route path="/booking/cancel" element={<CancelBooking />} />

      <Route path="/manage" element={<MyRides />} />
      <Route path="/manage/threshold" element={<RatingThreshold />} />
      <Route path="/manage/bookings" element={<ManageBookings />} />

      <Route path="/account" element={<Account />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
