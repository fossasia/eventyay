/**
 * Eventyay Telemetry Receiver - Google Apps Script
 * 
 * This script receives telemetry data from Eventyay instances and stores it
 * in a Google Sheet for analysis.
 * 
 * Deployment:
 * 1. Create a new Google Sheet
 * 2. Open Extensions > Apps Script
 * 3. Paste this code
 * 4. Set API_KEY in Script Properties (File > Project settings > Script properties)
 * 5. Deploy > New deployment > Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 6. Copy the deployment URL and configure in Eventyay settings
 */

// Sheet configuration
const SHEET_NAME = 'heartbeats';
const MAX_PAYLOAD_SIZE = 10000;  // bytes
const RATE_LIMIT_HOURS = 23;

/**
 * Handle POST requests from Eventyay instances.
 */
function doPost(e) {
  try {
    // 1. Check content length
    if (e.postData && e.postData.length > MAX_PAYLOAD_SIZE) {
      return jsonResponse({ok: false, error: 'payload_too_large'}, 413);
    }
    
    // 2. Authenticate
    const apiKey = PropertiesService.getScriptProperties().getProperty('API_KEY');
    if (!apiKey) {
      console.error('API_KEY not configured in Script Properties');
      return jsonResponse({ok: false, error: 'server_config_error'}, 500);
    }
    
    // Check X-API-Key header or api_key parameter
    const receivedKey = getApiKeyFromRequest(e);
    if (receivedKey !== apiKey) {
      return jsonResponse({ok: false, error: 'unauthorized'}, 401);
    }
    
    // 3. Parse JSON payload
    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseError) {
      return jsonResponse({ok: false, error: 'invalid_json'}, 400);
    }
    
    // 4. Validate required fields
    if (!payload.schema_version || !payload.instance_id) {
      return jsonResponse({ok: false, error: 'missing_required_fields'}, 400);
    }
    
    // 5. Check rate limit (once per 23 hours per instance)
    if (isRateLimited(payload.instance_id)) {
      return jsonResponse({ok: false, error: 'rate_limited', retry_after: RATE_LIMIT_HOURS * 3600}, 429);
    }
    
    // 6. Append row to sheet
    appendHeartbeat(payload);
    
    // 7. Return success
    return jsonResponse({ok: true, message: 'heartbeat_recorded'});
    
  } catch (err) {
    console.error('Error processing request:', err);
    return jsonResponse({ok: false, error: 'internal_error'}, 500);
  }
}

/**
 * Handle GET requests (for testing/status).
 */
function doGet(e) {
  return jsonResponse({
    ok: true,
    service: 'eventyay-telemetry-receiver',
    version: '1.0',
    message: 'Send POST requests with telemetry payload'
  });
}

/**
 * Extract API key from request headers or parameters.
 */
function getApiKeyFromRequest(e) {
  // Try to get from custom headers (note: Apps Script may not expose all headers)
  if (e.parameter && e.parameter.api_key) {
    return e.parameter.api_key;
  }
  
  // Check if we can access headers
  if (e.headers) {
    // Try various header formats
    return e.headers['X-API-Key'] || 
           e.headers['x-api-key'] || 
           e.headers['X-Api-Key'] ||
           null;
  }
  
  return null;
}

/**
 * Check if instance has sent a heartbeat recently.
 */
function isRateLimited(instanceId) {
  const sheet = getOrCreateSheet();
  const data = sheet.getDataRange().getValues();
  const cutoffTime = new Date(Date.now() - RATE_LIMIT_HOURS * 60 * 60 * 1000);
  
  // Check recent entries for this instance_id
  for (let i = data.length - 1; i >= 1; i--) {  // Skip header row
    const rowInstanceId = data[i][1];  // instance_id is column B
    const rowTimestamp = data[i][0];   // received_at is column A
    
    if (rowInstanceId === instanceId) {
      if (rowTimestamp instanceof Date && rowTimestamp > cutoffTime) {
        return true;  // Rate limited
      }
    }
  }
  
  return false;
}

/**
 * Append heartbeat data to the sheet.
 */
function appendHeartbeat(payload) {
  const sheet = getOrCreateSheet();
  const metrics = payload.metrics || {};
  
  const row = [
    new Date(),                                    // received_at_utc
    payload.instance_id || '',                     // instance_id
    payload.eventyay_version || '',                // eventyay_version
    payload.schema_version || '',                  // schema_version
    payload.python_version || '',                  // python_version
    payload.os_family || '',                       // os_family
    payload.database_type || '',                   // database_type
    payload.database_version || '',                // database_version
    payload.deployment_type || '',                 // deployment_type
    payload.storage_backend || '',                 // storage_backend
    metrics.events_bucket || '',                   // events_bucket
    metrics.live_events_bucket || '',              // live_events_bucket
    metrics.organizers_bucket || '',               // organizers_bucket
    metrics.orders_bucket || '',                   // orders_bucket
    metrics.paid_orders_bucket || '',              // paid_orders_bucket
    metrics.submissions_bucket || '',              // submissions_bucket
    JSON.stringify(payload.enabled_plugins || []), // enabled_plugins
    payload.celery_enabled || false,               // celery_enabled
    payload.redis_enabled || false,                // redis_enabled
    payload.maintainer_contact || '',              // maintainer_contact
    JSON.stringify(payload),                       // raw_payload (for debugging)
  ];
  
  sheet.appendRow(row);
}

/**
 * Get or create the heartbeats sheet with headers.
 */
function getOrCreateSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    
    // Add header row
    const headers = [
      'received_at_utc',
      'instance_id',
      'eventyay_version',
      'schema_version',
      'python_version',
      'os_family',
      'database_type',
      'database_version',
      'deployment_type',
      'storage_backend',
      'events_bucket',
      'live_events_bucket',
      'organizers_bucket',
      'orders_bucket',
      'paid_orders_bucket',
      'submissions_bucket',
      'enabled_plugins',
      'celery_enabled',
      'redis_enabled',
      'maintainer_contact',
      'raw_payload',
    ];
    
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  
  return sheet;
}

/**
 * Create a JSON response.
 */
function jsonResponse(data, statusCode = 200) {
  // Note: Apps Script doesn't allow setting HTTP status codes directly
  // The status is included in the response body for client handling
  const responseData = {...data, status_code: statusCode};
  
  return ContentService
    .createTextOutput(JSON.stringify(responseData))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Test function to verify sheet setup.
 */
function testSetup() {
  const sheet = getOrCreateSheet();
  console.log('Sheet name:', sheet.getName());
  console.log('Header row:', sheet.getRange(1, 1, 1, 21).getValues()[0]);
  
  // Test with sample payload
  const testPayload = {
    schema_version: '1',
    instance_id: 'test-' + new Date().getTime(),
    eventyay_version: '0.1',
    python_version: '3.11.0',
    os_family: 'Linux',
    database_type: 'postgresql',
    database_version: '15',
    deployment_type: 'docker',
    storage_backend: 'file',
    metrics: {
      events_bucket: '10-50',
      live_events_bucket: '1-10',
      organizers_bucket: '1-10',
      orders_bucket: '50-100',
      paid_orders_bucket: '10-50',
      submissions_bucket: '10-50',
    },
    enabled_plugins: ['badges', 'sendmail'],
    celery_enabled: true,
    redis_enabled: true,
  };
  
  appendHeartbeat(testPayload);
  console.log('Test heartbeat appended successfully!');
}
