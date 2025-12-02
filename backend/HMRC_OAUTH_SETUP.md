# HMRC VAT API OAuth Setup Guide

## Overview
The HMRC VAT API uses OAuth 2.0 with client credentials grant for server-to-server authentication.

## Prerequisites
1. HMRC Developer Hub account: https://developer.service.hmrc.gov.uk/
2. Application registered in HMRC Developer Hub
3. Client ID and Client Secret from your HMRC application

## Setup Steps

### 1. Register Application in HMRC Developer Hub

1. Go to https://developer.service.hmrc.gov.uk/
2. Sign in or create an account
3. Create a new application
4. Select the "VAT API" scope
5. Note down your:
   - **Client ID**
   - **Client Secret**

### 2. Configure Environment Variables

Add the following to your `.env` file:

```env
# HMRC VAT API OAuth Configuration
HMRC_CLIENT_ID=your_client_id_here
HMRC_CLIENT_SECRET=your_client_secret_here
HMRC_USE_OAUTH=true

# Alternative: If you have a server token instead of OAuth
# HMRC_SERVER_TOKEN=your_server_token_here
# HMRC_USE_OAUTH=false
```

### 3. OAuth Flow

The service automatically:
1. Requests an access token using client credentials
2. Caches the token until it expires
3. Refreshes the token 5 minutes before expiry
4. Uses the token for all API requests

### 4. API Endpoints

The service uses the following HMRC API endpoints:
- **Token Endpoint**: `https://api.service.hmrc.gov.uk/oauth/token`
- **VAT Check Endpoint**: `https://api.service.hmrc.gov.uk/organisations/vat/check-vat-number/{vatNumber}`

### 5. Testing

To test the OAuth integration:

```python
from app.services.hmrc_vat_service import HMRCVATService

service = HMRCVATService()
result = service.verify_vat_number("GB123456789")

if result:
    print(f"VAT Number: {result['vat_number']}")
    print(f"Valid: {result['valid']}")
    print(f"Business Name: {result['business_name']}")
```

## Troubleshooting

### Authentication Errors

**Error: 401 Unauthorized**
- Check that `HMRC_CLIENT_ID` and `HMRC_CLIENT_SECRET` are correct
- Verify your application has the "VAT API" scope enabled
- Ensure you're using the correct environment (sandbox vs production)

**Error: Token request failed**
- Check network connectivity
- Verify HMRC API is accessible
- Check application status in HMRC Developer Hub

### Rate Limits

HMRC API has rate limits:
- Sandbox: Usually more lenient
- Production: Check your application's rate limits in Developer Hub

The service will log warnings if rate limits are hit.

## Production Considerations

1. **Security**: Never commit `.env` file with credentials
2. **Token Storage**: Consider storing tokens in Redis for multi-instance deployments
3. **Error Handling**: Implement retry logic for transient failures
4. **Monitoring**: Monitor token refresh success rates
5. **Fallback**: Consider implementing a fallback mechanism if OAuth fails

## API Response Format

Successful response:
```json
{
  "vat_number": "GB123456789",
  "valid": true,
  "business_name": "Example Company Ltd",
  "address": "123 Business Street, London, SW1A 1AA",
  "registration_date": "2020-01-15",
  "status": "verified"
}
```

Not found response:
```json
{
  "vat_number": "GB123456789",
  "valid": false,
  "status": "not_found"
}
```

