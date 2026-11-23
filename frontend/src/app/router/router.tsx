import { createBrowserRouter, Navigate } from "react-router"
import { AdminLayout } from "@/app/layouts/AdminLayout"
import { PublicLayout } from "@/app/layouts/PublicLayout"
import { WorkspaceLayout } from "@/app/layouts/WorkspaceLayout"
import { GuestOnly, RequireAdmin, RequireAuth } from "@/app/router/guards"
import { NotFoundPage, RouteError } from "@/components/shared/states"
import {
  AcceptInvitationPage,
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
  VerifyEmailPage,
} from "@/features/auth/AuthPages"
import { AccountPage } from "@/features/account/AccountPage"
import { ArticlePage } from "@/features/articles/ArticlePage"
import { ArticlesPage, DiscoverPage } from "@/features/discovery/DiscoveryPages"
import {
  AuthorPage,
  AuthorsPage,
  CategoriesPage,
  CategoryPage,
  PublicationPage,
  PublicationsPage,
  TagPage,
  TagsPage,
} from "@/features/discovery/DirectoryPages"
import { HomePage } from "@/features/home/HomePage"
import { SearchPage } from "@/features/search/SearchPage"
import { NotificationPreferencesPage, NotificationsPage } from "@/features/notifications/NotificationsPage"
import { ArticleListPage } from "@/features/editor/ArticleListPage"
import { EditorPage } from "@/features/editor/EditorPage"
import { WorkspaceHome } from "@/features/editor/WorkspaceHome"
import { MediaPage } from "@/features/media/MediaPage"
import { AuthorAnalyticsPage } from "@/features/analytics/AuthorAnalyticsPage"
import {
  MyPublicationsPage,
  NewPublicationPage,
  PublicationManagePage,
} from "@/features/publications/PublicationWorkspace"
import {
  AdminAnalyticsPage,
  AdminArticlesPage,
  AdminCategoriesPage,
  AdminCommentsPage,
  AdminDeliveryPage,
  AdminHome,
  AdminMediaPage,
  AdminReportsPage,
  AdminSearchPage,
  AdminTagsPage,
} from "@/features/administration/AdminPages"
import { MyCommentsPage } from "@/features/comments/MyCommentsPage"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <PublicLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "articles", element: <ArticlesPage /> },
      { path: "articles/:slug", element: <ArticlePage /> },
      { path: "discover/:feed", element: <DiscoverPage /> },
      { path: "authors", element: <AuthorsPage /> },
      { path: "authors/:username", element: <AuthorPage /> },
      { path: "publications", element: <PublicationsPage /> },
      { path: "publications/:slug", element: <PublicationPage /> },
      { path: "categories", element: <CategoriesPage /> },
      { path: "categories/:slug", element: <CategoryPage /> },
      { path: "tags", element: <TagsPage /> },
      { path: "tags/:slug", element: <TagPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "verify-email", element: <VerifyEmailPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
      {
        element: <GuestOnly />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "register", element: <RegisterPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          { path: "account", element: <AccountPage /> },
          { path: "notifications", element: <NotificationsPage /> },
          { path: "notifications/preferences", element: <NotificationPreferencesPage /> },
          { path: "invitations/accept", element: <AcceptInvitationPage /> },
          {
            path: "workspace",
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <WorkspaceHome /> },
              { path: "articles", element: <ArticleListPage /> },
              { path: "articles/new", element: <EditorPage /> },
              { path: "articles/:id", element: <EditorPage /> },
              { path: "media", element: <MediaPage /> },
              { path: "analytics", element: <AuthorAnalyticsPage /> },
              { path: "publications", element: <MyPublicationsPage /> },
              { path: "publications/new", element: <NewPublicationPage /> },
              { path: "publications/:id", element: <PublicationManagePage /> },
              { path: "comments", element: <MyCommentsPage /> },
            ],
          },
          {
            element: <RequireAdmin />,
            children: [
              {
                path: "admin",
                element: <AdminLayout />,
                children: [
                  { index: true, element: <AdminHome /> },
                  { path: "analytics", element: <AdminAnalyticsPage /> },
                  { path: "articles", element: <AdminArticlesPage /> },
                  { path: "categories", element: <AdminCategoriesPage /> },
                  { path: "tags", element: <AdminTagsPage /> },
                  { path: "comments", element: <AdminCommentsPage /> },
                  { path: "reports", element: <AdminReportsPage /> },
                  { path: "media", element: <AdminMediaPage /> },
                  { path: "search", element: <AdminSearchPage /> },
                  { path: "delivery", element: <AdminDeliveryPage /> },
                ],
              },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
])
