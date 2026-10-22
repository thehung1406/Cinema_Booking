import { Route, Routes, useLocation } from "react-router-dom";
import NotFound from "./components/NotFound";
import LoginPage from "./components/LoginPage";
import HomePage from "./components/HomePage";
import MainHomePage from "./components/MainHomePage";
import Contact from "./components/Contact";
import About from "./components/About";
import Movie from "./components/Movie";
import CinemaList from "./components/CinemaList";
import UserInfor from "./components/UserInfor";
import SeatSelection from "./components/SeatSelection";
import FoodSelection from "./components/FoodSelection";
import MovieDetail from "./components/MovieDetail";
import TicketBooking from "./components/TicketBooking";
import VNPayReturn from "./components/VNPayReturn";
import PaymentPage from "./components/PaymentPage";
import AIAssistant from "./components/AIAssistant";
import ReviewModeration from "./components/ReviewModeration";
import AdminLayout from "./components/admin/AdminLayout";
import { FilmsPage, RoomsPage, SeatsPage, ShowtimesPage, PricesPage } from "./components/admin/AdminCatalogPages";
import { EmployeesPage, RolesPage } from "./components/admin/AdminPeoplePages";
import { DocumentsPage, ReportsPage } from "./components/admin/AdminKnowledgeReports";



function App() {
  const location = useLocation();
  return (
    <div>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route path="films" element={<FilmsPage />} />
          <Route path="rooms" element={<RoomsPage />} />
          <Route path="rooms/:roomId/seats" element={<SeatsPage />} />
          <Route path="showtimes" element={<ShowtimesPage />} />
          <Route path="prices" element={<PricesPage />} />
          <Route path="employees" element={<EmployeesPage />} />
          <Route path="roles" element={<RolesPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="/" element={<HomePage />}>
          <Route index element={<MainHomePage />} />
          <Route path="cinema" element={<CinemaList />} />
          <Route path="contact" element={<Contact />} />
          <Route path="about" element={<About />} />
          <Route path="movie" element={<Movie />} />
          <Route path="movies" element={<Movie />} />
          <Route path="movie/:id" element={<MovieDetail />} />
          <Route path="MovieDetail/:id" element={<MovieDetail />} />
          <Route path="ticket-booking" element={<TicketBooking />} />
          <Route path="TicketBooking" element={<TicketBooking />} />
          <Route path="booking" element={<TicketBooking />} />
          <Route path="payment/:bookingId" element={<PaymentPage />} />
          <Route path="payment-result" element={<VNPayReturn />} />
          <Route path="seat-selection/:showtimeId" element={<SeatSelection />} />
          <Route path="food-selection/:showtimeId" element={<FoodSelection />} />
          <Route path="user-info" element={<UserInfor />} />
          <Route path="userInfo" element={<UserInfor />} />
          <Route path="review-moderation" element={<ReviewModeration />} />
        </Route>
        <Route path="login" element={<LoginPage />} />
        <Route path="loginPage" element={<LoginPage />} />
        <Route path="loginpage" element={<LoginPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {!location.pathname.startsWith("/admin") && <AIAssistant />}
    </div>
  );
}
export default App;
