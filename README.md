

Alien Okta App

Secure Identity Verification and Rewards Eligibility Platform

Overview

Alien Okta App is a secure identity driven backend application that verifies user authentication and enforces access policies using Okta. The system ensures that only authorized users can access protected endpoints and receive rewards based on defined eligibility logic.

The application demonstrates real world Identity and Access Management implementation using modern cloud native architecture.

⸻

Architecture

Frontend or Client → FastAPI Backend → Okta Authentication → Role Based Access Control → Business Logic → Cloud Deployment

Deployed on Google Cloud Run with secure OAuth 2.0 based authentication flows.

⸻

Key Features

• Okta Single Sign On integration
• OAuth 2.0 and OpenID Connect implementation
• Role Based Access Control
• Secure reward eligibility validation
• REST API endpoints with protected routes
• Cloud native deployment using Google Cloud Run
• Environment variable based secret management

⸻

Tech Stack

Backend: FastAPI
Authentication: Okta Workforce Identity
Protocols: OAuth 2.0, OpenID Connect
Cloud: Google Cloud Run
Language: Python
Security: JWT validation, access token verification

⸻

Authentication Flow
	1.	User attempts to access protected endpoint
	2.	User is redirected to Okta for authentication
	3.	Okta validates credentials and returns ID token and access token
	4.	Backend verifies JWT signature and claims
	5.	Access granted based on role or group membership

⸻

API Endpoints

GET /public
Accessible without authentication

GET /protected
Requires valid Okta access token

POST /reward
Validates user eligibility and processes reward logic

⸻

Security Design

• JWT token validation using Okta public keys
• Audience and issuer claim verification
• Scope based authorization checks
• Secure environment configuration
• Principle of least privilege enforcement

⸻

Setup Instructions

1. Clone Repository

git clone https://github.com/yourusername/alien-okta-app.git
cd alien-okta-app

2. Install Dependencies

pip install -r requirements.txt

3. Configure Environment Variables

Create a .env file:

OKTA_DOMAIN=your-org.okta.com
OKTA_AUDIENCE=api://default
OKTA_CLIENT_ID=your_client_id

4. Run Application

uvicorn main:app --reload


⸻

Deployment

The application is containerized and deployed on Google Cloud Run.

Steps:
	1.	Build Docker image
	2.	Push to Google Container Registry
	3.	Deploy to Cloud Run
	4.	Configure environment variables securely

⸻

Use Cases

• Identity based reward distribution
• Secure SaaS access management
• API protection with enterprise SSO
• IAM portfolio demonstration project

⸻

What This Project Demonstrates

• Practical implementation of Okta SSO
• Secure API architecture
• Understanding of OAuth and OIDC flows
• Real world IAM application design
• Cloud native deployment skills

⸻

Future Enhancements

• Multi Factor Authentication enforcement
• Lifecycle management integration
• Admin dashboard
• Logging and monitoring with SIEM tools
• SCIM provisioning support

⸻

