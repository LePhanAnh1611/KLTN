import { useLayoutEffect } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';

import AppLayout from './components/AppLayout';
import Achievements from './pages/Achievements';
import Admin from './pages/Admin';
import Community from './pages/Community';
import Dashboard from './pages/Dashboard';
import Discover from './pages/Discover';
import FinalTest from './pages/FinalTest';
import Dictionary from './pages/Dictionary';
import Conversation from './pages/Conversation';
import Games from './pages/Games';
import Login from './pages/Login';
import Placement from './pages/Placement';
import Profile from './pages/Profile';
import Notebook from './pages/Notebook';
import Pronunciation from './pages/Pronunciation';
import Speaking from './pages/Speaking';
import Shadowing from './pages/Shadowing';
import ShadowingVideo from './pages/ShadowingVideo';
import PublicProfile from './pages/PublicProfile';
import Roadmap from './pages/Roadmap';
import Settings from './pages/Settings';
import VerifyEmail from './pages/VerifyEmail';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Progress from './pages/Progress';
import Register from './pages/Register';
import Reviews from './pages/Reviews';
import ReviewStudy from './pages/ReviewStudy';
import Study from './pages/Study';
import WordSetDetail from './pages/WordSetDetail';
import WordSetFromPdf from './pages/WordSetFromPdf';
import WordSets from './pages/WordSets';

/**
 * Đổi trang là về đầu trang. Mặc định trình duyệt giữ nguyên vị trí cuộn của
 * trang trước (VD đang giữa Trang chủ, sang Cộng đồng cũng rơi vào giữa) —
 * người dùng thử phản ánh 2026-10-26. Chỉ theo pathname: đổi ?query (lọc,
 * phân trang) thì vẫn giữ chỗ đang xem.
 */
function ScrollToTop() {
  const { pathname } = useLocation();
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname]);
  return null;
}

function App() {
  return (
    <>
    <ScrollToTop />
    <Routes>
      {/* Trang công khai (không có khung app) */}
      <Route path="/register" element={<Register />} />
      <Route path="/login" element={<Login />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Phiên học toàn màn hình (không có sidebar) */}
      <Route path="/word-sets/:id/study/:mode" element={<Study />} />
      {/* "Học N từ mới" ở trang chủ — đúng các từ đã gợi ý (?ids=…), xuyên thư viện */}
      <Route path="/study/today" element={<Study />} />
      <Route path="/reviews/study" element={<ReviewStudy />} />
      <Route path="/final-test" element={<FinalTest />} />

      {/* Khu vực có khung app (sidebar + topbar), yêu cầu đăng nhập */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/word-sets" element={<WordSets />} />
        {/* Khai TRƯỚC "/:id" cho dễ đọc — đoạn tĩnh vẫn thắng đoạn động (UC-87) */}
        <Route path="/word-sets/from-pdf" element={<WordSetFromPdf />} />
        <Route path="/word-sets/:id" element={<WordSetDetail />} />
        <Route path="/roadmap" element={<Roadmap />} />
        <Route path="/placement" element={<Placement />} />
        <Route path="/pronunciation" element={<Pronunciation />} />
        {/* Nói tự do: gỡ khỏi menu (2026-10-27) nhưng giữ route để liên kết cũ không vỡ */}
        <Route path="/speaking" element={<Speaking />} />
        <Route path="/shadowing" element={<Shadowing />} />
        <Route path="/shadowing/:id" element={<ShadowingVideo />} />
        <Route path="/notebook" element={<Notebook />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/dictionary" element={<Dictionary />} />
        <Route path="/games" element={<Games />} />
        <Route path="/conversation" element={<Conversation />} />
        <Route path="/community" element={<Community />} />
        <Route path="/users/:id" element={<PublicProfile />} />
        <Route path="/reviews" element={<Reviews />} />
        <Route path="/progress" element={<Progress />} />
        <Route path="/achievements" element={<Achievements />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
    </>
  );
}

export default App;
