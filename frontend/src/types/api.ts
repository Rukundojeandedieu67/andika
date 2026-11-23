export type UserRole = "reader" | "author" | "administrator"
export type PostStatus = "draft" | "published" | "archived"
export type EditorialStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "changes_requested"
  | "approved"
  | "published"
export type CommentStatus = "pending" | "approved" | "hidden" | "rejected"
export type ReportReason =
  | "spam"
  | "harassment"
  | "hate_speech"
  | "misinformation"
  | "inappropriate_content"
  | "other"
export type ReportStatus = "open" | "resolved" | "dismissed"
export type PublicationVisibility = "public" | "private"
export type PublicationStatus = "active" | "suspended" | "archived"
export type MembershipRole = "owner" | "editor" | "author" | "contributor"
export type MembershipStatus = "pending" | "active" | "suspended" | "removed"
export type InvitationStatus = "pending" | "accepted" | "expired" | "revoked"
export type InviteRole = "editor" | "author" | "contributor"
export type MediaStatus = "processing" | "ready" | "failed"
export type ArticleFeed = "latest" | "trending" | "popular" | "discussed" | "featured"
export type SearchType = "all" | "articles" | "authors" | "publications" | "categories" | "tags"
export type ArticleSort = "relevance" | "newest" | "oldest" | "most_viewed" | "most_commented"
export type AnalyticsSort = "views" | "comments" | "published_at"
export type AnalyticsPeriod = "day" | "week" | "month"
export type NotificationType =
  | "comment_received"
  | "comment_reply_received"
  | "comment_approved"
  | "comment_hidden"
  | "comment_rejected"
  | "publication_invitation_received"
  | "publication_invitation_accepted"
  | "publication_member_role_changed"
  | "publication_member_suspended"
  | "publication_member_removed"
  | "publication_ownership_transferred"
  | "article_submitted_for_review"
  | "article_review_started"
  | "article_changes_requested"
  | "article_approved"
  | "article_published"
  | "article_unpublished"

export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
  details?: Array<{ loc: Array<string | number>; message: string }>
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface AuthorPublic {
  id: string
  username: string
  full_name: string | null
  avatar_url: string | null
  bio: string | null
}

export interface UserPublic extends AuthorPublic {
  email: string
  role: UserRole
  is_active: boolean
  is_verified: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export interface AccessTokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  refresh_token: string
  user: UserPublic
}

export interface MessageResponse {
  message: string
}

export interface CategoryBrief {
  id: string
  name: string
  slug: string
  description: string | null
}

export interface CategoryNode extends CategoryBrief {
  children: CategoryNode[]
}

export interface CategoryDetail extends CategoryBrief {
  is_active: boolean
  parent: CategoryBrief | null
  children: CategoryBrief[]
}

export interface CategoryAdmin extends CategoryBrief {
  parent_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TagBrief {
  id: string
  name: string
  slug: string
  description: string | null
}

export interface TagAdmin extends TagBrief {
  created_at: string
  updated_at: string
}

export interface MediaVariant {
  kind: string
  url: string
  width: number
  height: number
  mime_type: string
  file_size: number
}

export interface MediaRead {
  id: string
  original_filename: string
  mime_type: string
  file_extension: string
  file_size: number
  width: number | null
  height: number | null
  alt_text: string | null
  caption: string | null
  title: string | null
  status: MediaStatus
  created_at: string
  updated_at: string
  variants: MediaVariant[]
}

export interface MediaAdminRead extends MediaRead {
  owner_id: string
}

export interface FeaturedImage {
  id: string
  alt_text: string | null
  caption: string | null
  title: string | null
  width: number | null
  height: number | null
  mime_type: string
  variants: MediaVariant[]
}

export interface PostRead {
  id: string
  title: string
  slug: string
  subtitle: string | null
  excerpt: string | null
  content: string
  featured_image: string | null
  status: PostStatus
  is_featured: boolean
  allow_comments: boolean
  meta_title: string | null
  meta_description: string | null
  reading_time: number
  created_at: string
  updated_at: string
  published_at: string | null
  author: AuthorPublic
  publication_id: string | null
  editorial_status: EditorialStatus | null
  category: CategoryBrief | null
  tags: TagBrief[]
  featured_image_media: FeaturedImage | null
}

export interface PostRevision {
  id: string
  post_id: string
  edited_by: string
  title: string
  excerpt: string | null
  content: string
  revision_number: number
  created_at: string
}

export interface EditorialEvent {
  id: string
  action: string
  from_status: string | null
  to_status: string
  reason: string | null
  created_at: string
  actor: AuthorPublic
}

export interface EditorialPostDetail extends PostRead {
  events: EditorialEvent[]
}

export interface ArticleCard {
  id: string
  title: string
  slug: string
  excerpt: string | null
  featured_image: string | null
  published_at: string | null
  reading_time: number
  comment_count: number
  view_count: number
  author: AuthorPublic
  publication: { id: string; name: string; slug: string } | null
  category: CategoryBrief | null
  tags: TagBrief[]
}

export interface AuthorCard {
  id: string
  username: string
  full_name: string | null
  avatar_url: string | null
  bio: string | null
  article_count: number
  categories: string[]
}

export interface PublicationCard {
  id: string
  name: string
  slug: string
  description: string | null
  created_at: string
  article_count: number
  categories: string[]
  tags: string[]
}

export interface TaxonomyCard {
  id: string
  name: string
  slug: string
  article_count: number
}

export interface SearchResponse {
  query: string
  articles: Page<ArticleCard>
  authors: Page<AuthorCard>
  publications: Page<PublicationCard>
  categories: Page<TaxonomyCard>
  tags: Page<TaxonomyCard>
}

export interface Suggestion {
  type: "article" | "author" | "publication" | "category" | "tag"
  id: string
  label: string
  slug: string | null
}

export interface SearchStats {
  since: string
  total: number
  by_type: Array<{ search_type: string; count: number }>
  top_queries: Array<{ query: string; count: number }>
}

export interface Branding {
  media_id: string
  url: string | null
}

export interface PublicationPublic {
  id: string
  name: string
  slug: string
  description: string | null
  website_url: string | null
  contact_email: string | null
  logo: Branding | null
  cover: Branding | null
  owner: AuthorPublic
  created_at: string
}

export interface PublicationMineItem {
  id: string
  name: string
  slug: string
  visibility: PublicationVisibility
  status: PublicationStatus
  role: MembershipRole
  membership_status: MembershipStatus
}

export interface PublicationManage extends PublicationPublic {
  visibility: PublicationVisibility
  status: PublicationStatus
  requires_review: boolean
  editors_can_invite: boolean
  caller_role: MembershipRole
  member_count: number
}

export interface MemberRead {
  id: string
  role: MembershipRole
  status: MembershipStatus
  joined_at: string
  user: AuthorPublic
}

export interface InvitationRead {
  id: string
  email: string
  role: MembershipRole
  status: InvitationStatus
  expires_at: string
  accepted_at: string | null
  created_at: string
  invited_by: AuthorPublic
}

export interface InvitationCreated {
  invitation: InvitationRead
  email_delivery: "sent" | "not_configured" | "failed"
  message: string
}

export interface PublicationAudit {
  id: string
  action: string
  previous_value: string | null
  new_value: string | null
  created_at: string
  actor: AuthorPublic
  target: AuthorPublic | null
}

export interface CommentRead {
  id: string
  body: string
  created_at: string
  edited_at: string | null
  author: AuthorPublic
  replies: CommentRead[]
}

export interface CommentOwned {
  id: string
  post_id: string
  parent_id: string | null
  body: string
  status: CommentStatus
  created_at: string
  updated_at: string
  edited_at: string | null
  author: AuthorPublic
}

export interface ModerationComment {
  id: string
  post_id: string
  parent_id: string | null
  author_id: string
  body: string
  status: CommentStatus
  created_at: string
  updated_at: string
  edited_at: string | null
  deleted_at: string | null
  author: AuthorPublic
}

export interface ReportRead {
  id: string
  comment_id: string
  reason: ReportReason
  description: string | null
  status: ReportStatus
  created_at: string
  reviewed_at: string | null
  reporter: AuthorPublic
}

export interface ModerationLog {
  id: string
  moderator_id: string
  comment_id: string
  action: string
  previous_status: string
  new_status: string
  reason: string | null
  created_at: string
}

export interface NotificationRead {
  id: string
  type: NotificationType
  title: string
  message: string
  resource_type: string | null
  resource_id: string | null
  action_url: string | null
  metadata: Record<string, unknown>
  is_read: boolean
  read_at: string | null
  created_at: string
  actor: AuthorPublic | null
}

export interface NotificationPreferences {
  in_app_comments: boolean
  email_comments: boolean
  in_app_publications: boolean
  email_publications: boolean
  in_app_editorial: boolean
  email_editorial: boolean
  in_app_account: boolean
  email_account: boolean
}

export interface DeliveryFailure {
  id: string
  notification_type: NotificationType
  attempts: number
  last_error: string | null
  updated_at: string
}

export interface DeliveryStats {
  pending: number
  sending: number
  sent: number
  failed: number
  not_configured: number
  failed_jobs: DeliveryFailure[]
}

export interface ReportWindow {
  date_from: string
  date_to: string
  timezone: "UTC"
}

export interface PeriodComparison {
  date_from: string
  date_to: string
  views: number
  approved_comments: number
  articles_published: number
}

export interface ArticlePerformance {
  id: string
  title: string
  slug: string
  published_at: string
  publication: { id: string; name: string; slug: string } | null
  views: number
  approved_comments: number
  engagement_rate: number
}

export interface ArticlePerformancePage extends Page<ArticlePerformance> {
  sort: AnalyticsSort
  window: ReportWindow
  engagement_rate_formula: string
}

export interface PublicationArticlePage extends ArticlePerformancePage {
  scope: "publication" | "own"
}

export interface AuthorOverview {
  published_articles: number
  publication_articles: number
  total_views: number
  total_approved_comments: number
  period_views: number
  period_approved_comments: number
  average_views_per_article: number
  window: ReportWindow
  comparison: PeriodComparison | null
  limitations: string[]
}

export interface SeriesPoint {
  bucket_start: string
  views: number
  approved_comments: number
  articles_published: number
}

export interface TimeSeries {
  period: AnalyticsPeriod
  timezone: "UTC"
  week_starts_on: "monday"
  date_from: string
  date_to: string
  points: SeriesPoint[]
  limitations: string[]
}

export interface AuthorContribution {
  user_id: string
  username: string
  full_name: string | null
  published_articles: number
  views: number
  approved_comments: number
  first_published_at: string | null
  last_published_at: string | null
}

export interface AuthorContributionPage extends Page<AuthorContribution> {
  scope: "publication" | "own"
  window: ReportWindow
}

export interface PublicationOverview {
  publication_id: string
  scope: "publication" | "own"
  published_articles: number
  total_views: number
  total_approved_comments: number
  active_authors: number
  period_views: number
  period_approved_comments: number
  period_articles_published: number
  average_views_per_article: number
  window: ReportWindow
  comparison: PeriodComparison | null
  limitations: string[]
}

export interface AdminPeriodComparison extends PeriodComparison {
  registrations: number
  publications_created: number
}

export interface AdminOverview {
  registered_users: number
  active_users: number
  active_user_definition: string
  publications: number
  active_public_publications: number
  published_articles: number
  total_views: number
  total_approved_comments: number
  period_registrations: number
  period_articles_published: number
  period_publications: number
  window: ReportWindow
  comparison: AdminPeriodComparison | null
  limitations: string[]
}

export interface AdminSeriesPoint extends SeriesPoint {
  registrations: number
  publications_created: number
}

export interface AdminTimeSeries {
  period: AnalyticsPeriod
  timezone: "UTC"
  week_starts_on: "monday"
  date_from: string
  date_to: string
  points: AdminSeriesPoint[]
  limitations: string[]
}

export interface ContentSlice {
  published_articles: number
  views: number
  approved_comments: number
  engagement_rate: number
}

export interface AdminContent {
  independent: ContentSlice
  public_publication: ContentSlice
  other_publication: ContentSlice
  top_public_articles: Array<{
    id: string
    title: string
    slug: string
    views: number
    approved_comments: number
    engagement_rate: number
  }>
  window: ReportWindow
  engagement_rate_formula: string
  limitations: string[]
}
