import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { AppLayout, PublicLayout } from "../layouts/AppLayout";
import { Spinner } from "../components/ui/Feedback";
import { LandingPage } from "../pages/LandingPage";
import { HowItWorksPage } from "../pages/HowItWorksPage";
import { PrivacyPage } from "../pages/PrivacyPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage, RegisterPage } from "../features/auth/AuthPages";
import { ProfilePage } from "../features/profiles/ProfilePage";
import { PublicProfilePage } from "../features/profiles/PublicProfilePage";
import { SettingsPage } from "../features/profiles/SettingsPage";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { ProjectDetailPage } from "../features/projects/ProjectDetailPage";
import { ProjectWizardPage } from "../features/projects/ProjectWizardPage";
import { RecommendationsPage } from "../features/recommendations/RecommendationsPage";
import { InvitationsPage } from "../features/teams/InvitationsPage";
import { MessagesPage } from "../features/messaging/MessagesPage";
import { ResearchPage } from "../features/research/ResearchPage";
import { JudgingPage } from "../features/research/JudgingPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready)
    return (
      <div className="p-8">
        <Spinner />
      </div>
    );
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (ready && user) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route element={user ? <AppLayout /> : <PublicLayout />}>
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
      </Route>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<PublicOnly><LandingPage /></PublicOnly>} />
        <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><RegisterPage /></PublicOnly>} />
      </Route>
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/students/:userId" element={<PublicProfilePage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/new" element={<ProjectWizardPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/projects/:projectId/edit" element={<ProjectWizardPage />} />
        <Route path="/projects/:projectId/recommendations" element={<RecommendationsPage />} />
        <Route path="/invitations" element={<InvitationsPage />} />
        <Route path="/messages" element={<MessagesPage />} />
        <Route path="/messages/:conversationId" element={<MessagesPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/research/judging/:scenarioId" element={<JudgingPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
