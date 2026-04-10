# Changelog

All notable changes to the WealthWise Finance Tracker project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added

#### Authentication
- User registration with email validation and secure password hashing
- JWT-based authentication with access and refresh token support
- Login and logout functionality with token revocation
- Password reset flow with email verification
- Role-based access control (Admin, User)

#### Transaction Management
- Full CRUD operations for financial transactions (income and expenses)
- Transaction categorization with user-defined categories
- Date range filtering and search across transactions
- Pagination support for transaction listings
- Bulk transaction operations

#### Category Management
- Create, read, update, and delete custom transaction categories
- Default system categories seeded on first run
- Category-based transaction grouping and filtering
- Icon and color assignment for categories

#### Budget Management
- Monthly and custom period budget creation per category
- Budget tracking with real-time spending calculations
- Budget threshold alerts when approaching or exceeding limits
- Budget vs. actual spending comparison

#### Dashboard & Analytics
- Overview dashboard with income, expenses, and net balance summary
- Monthly spending trends with category breakdowns
- Visual spending distribution by category
- Recent transactions feed on the dashboard
- Period-over-period comparison metrics

#### CSV Export
- Export transactions to CSV format with customizable date ranges
- Category and date filters applied to exports
- Downloadable file generation with proper headers

#### Admin Controls
- Admin user management panel for viewing and managing all users
- Ability to activate and deactivate user accounts
- System-wide transaction and category statistics
- Admin-only endpoints protected by role-based middleware

#### Deployment & Infrastructure
- FastAPI application with async SQLAlchemy and SQLite/PostgreSQL support
- Pydantic v2 schemas for request and response validation
- CORS configuration for frontend integration
- Vercel deployment configuration with serverless functions
- Environment-based configuration using Pydantic Settings
- Structured logging throughout the application
- Comprehensive API documentation via Swagger UI and ReDoc