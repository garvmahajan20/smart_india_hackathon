import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { NewVerificationPage } from "../pages/NewVerificationPage";
import { VerificationWorkbenchPage } from "../pages/VerificationWorkbenchPage";
import { ReviewQueuePage } from "../pages/ReviewQueuePage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="verify/new" element={<NewVerificationPage />} />
          <Route path="verification/new" element={<NewVerificationPage />} />
          <Route path="verification/:id" element={<VerificationWorkbenchPage />} />
          <Route path="review" element={<ReviewQueuePage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};
