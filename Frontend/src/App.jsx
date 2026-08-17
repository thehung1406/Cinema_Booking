import { Route, Routes } from "react-router-dom";
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
import MovieDetail from "./components/MovieDetail";
import TicketBooking from "./components/TicketBooking";
import VNPayReturn from "./components/VNPayReturn";
import PaymentPage from "./components/PaymentPage";



function App() {
  return (
    <div>
      <Routes>
        <Route path="/" element={<HomePage />}>
          <Route index="/" element={<MainHomePage />} />
          <Route path="cinema" element={<CinemaList/>} />
          <Route path="contact" element={<Contact />} />
          <Route path="about" element=<About /> />
          <Route path="movie" element=<Movie/> /> 
          <Route path="/payment/:bookingId" element={<PaymentPage />} />
          <Route path="/payment-result" element={<VNPayReturn />} />
          <Route path="/MovieDetail/:id" element={<MovieDetail />} />
          <Route path="/seat-selection/:showtimeId" element={<SeatSelection />} />
          <Route path="TicketBooking" element={<TicketBooking/>}/>
          <Route path="userInfo" element={<UserInfor/>}/>
        </Route>
          <Route path="*" element={<NotFound />} />
        <Route path="loginPage" element={<LoginPage />} />
      </Routes>
    </div>
  );
}
export default App;
