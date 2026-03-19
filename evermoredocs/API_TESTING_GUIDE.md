# Evermore (AutoTradeTech) — Complete API Testing Guide

> **Version:** 1.0
> **Date:** 2026-03-18
> **Source Documentation:** `RESTAPI.1.pdf`, `MT.Data.Feed.API_V1.pdf`
> **Author:** QA Engineering

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Authentication Flow](#2-authentication-flow)
3. [REST API Endpoints](#3-rest-api-endpoints)
   - 3.1 [LoginRequest](#31-loginrequest)
   - 3.2 [OrderEntry](#32-orderentry)
   - 3.3 [OrderStatusRequest](#33-orderstatusrequest)
   - 3.4 [ModifyRequest](#34-modifyrequest)
   - 3.5 [CancelRequest](#35-cancelrequest)
   - 3.6 [OrderBookRequest](#36-orderbookrequest)
   - 3.7 [TradeBookRequest](#37-tradebookrequest)
   - 3.8 [PositionRequest](#38-positionrequest)
4. [WebSocket Data Feed API](#4-websocket-data-feed-api)
   - 4.1 [Login / Logout](#41-login--logout)
   - 4.2 [TokenRequest (Subscribe/Unsubscribe)](#42-tokenrequest)
   - 4.3 [MarketData Response](#43-marketdata-response)
   - 4.4 [Depth Response](#44-depth-response)
   - 4.5 [Greek Response](#45-greek-response)
   - 4.6 [IndexData Response](#46-indexdata-response)
   - 4.7 [OChain (Option Chain)](#47-ochain-option-chain)
   - 4.8 [CandleBar Response](#48-candlebar-response)
   - 4.9 [FeedStatus / Info](#49-feedstatus--info)
5. [End-to-End Test Scenarios](#5-end-to-end-test-scenarios)
6. [Common Issues & Troubleshooting](#6-common-issues--troubleshooting)
7. [Field Name Casing Reference](#7-field-name-casing-reference)

---

## 1. Environment Setup

### Endpoints

| Purpose | URL |
|---------|-----|
| REST API Base | `http://192.168.6.164:16006` |
| WebSocket (UAT — documented) | `ws://115.242.15.134:19101` |
| WebSocket (UAT — verified working) | `ws://192.168.6.164:19101` ⚠️ |
| WebSocket (Live) | `wss://feedapi.com` |

### Credentials

| Field | Value |
|-------|-------|
| LoginId | `DAKS` |
| Password | `a@3333333333` |

### Tools Required

| Tool | Purpose | Install |
|------|---------|---------|
| **cURL** | REST API testing from CLI | Pre-installed on most OS |
| **Postman** | GUI API testing | [postman.com](https://www.postman.com/) |
| **wscat** | WebSocket testing from CLI | `npm install -g wscat` |
| **websocat** | Alternative WebSocket CLI | `cargo install websocat` |
| **jq** | JSON response formatting | `apt install jq` / `brew install jq` |

### Quick Connectivity Test

```bash
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/LoginRequest \
  -H "Content-Type: application/json" \
  -d '{"LoginId":"DAKS","Password":"a@3333333333"}' | jq .
```

**Expected response:**
```json
{
  "UniqueId": 29,
  "RefNo": "MxTmI8eE3kiVrsaqOjuATaRFdtxCPaU8",
  "Error": null
}
```

> **Verified:** Login succeeded on 2026-03-18 with HTTP 200. Server: `Microsoft-HTTPAPI/2.0`.

---

## 2. Authentication Flow

```
┌─────────┐    POST /LoginRequest    ┌──────────┐
│  Client  │ ──────────────────────► │  Server  │
│          │    {LoginId, Password}  │          │
│          │ ◄────────────────────── │          │
│          │  {UniqueId, RefNo}      │          │
└─────────┘                          └──────────┘
      │
      │  Use UniqueId + RefNo in ALL subsequent requests
      │
      ▼
┌─────────────────────────────────────────────────┐
│  OrderEntry / ModifyRequest / CancelRequest     │
│  OrderBookRequest / TradeBookRequest            │
│  PositionRequest / OrderStatusRequest           │
└─────────────────────────────────────────────────┘
```

**Key rules:**
- Every login generates a **new RefNo** (previous sessions stay valid until server-side expiry)
- `UniqueId = 0` and `RefNo = ""` indicate **failed login**
- All subsequent API calls require both `UniqueId` (int) and `RefNo` (string)
- There is **no explicit logout** endpoint for REST — sessions expire server-side

---

## 3. REST API Endpoints

> **Base URL:** `http://192.168.6.164:16006`
> **Content-Type:** `application/json` (all requests)
> **Method:** `POST` (all endpoints)

---

### 3.1 LoginRequest

**Endpoint:** `POST /api/PublicAPI/LoginRequest`

**Description:** Authenticates user and returns a session token (RefNo) plus a unique identifier (UniqueId). These must be passed to all subsequent API calls.

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `LoginId` | string | ✅ | Username |
| `Password` | string | ✅ | Password |

#### Response Schema (LogonResponse)

| Field | Type | Description |
|-------|------|-------------|
| `UniqueId` | int | Unique session identifier (0 on failure) |
| `RefNo` | string | Auth token string (empty on failure) |
| `Error` | string/null | Error message (null on success) |

#### cURL Command

```bash
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/LoginRequest \
  -H "Content-Type: application/json" \
  -d '{
    "LoginId": "DAKS",
    "Password": "a@3333333333"
  }' | jq .
```

#### Live Test Result

```json
{
  "UniqueId": 29,
  "RefNo": "MxTmI8eE3kiVrsaqOjuATaRFdtxCPaU8",
  "Error": null
}
```

> HTTP 200 | Server: Microsoft-HTTPAPI/2.0

#### Edge Cases

- Wrong password → `UniqueId: 0`, `RefNo: ""`, `Error` contains message
- Empty LoginId → Error response
- Empty Password → Error response
- Special characters in password → Should work (tested: `a@3333333333`)
- Repeated logins → Each returns a **different RefNo**
- Concurrent logins with same credentials → Both get valid sessions

#### Test Cases

| ID | Scenario | Input | Expected | Type |
|----|----------|-------|----------|------|
| L-01 | Valid login | `{"LoginId":"DAKS","Password":"a@3333333333"}` | `UniqueId > 0`, `RefNo` non-empty, `Error` null | ✅ Success |
| L-02 | Wrong password | `{"LoginId":"DAKS","Password":"wrong"}` | `UniqueId: 0`, `RefNo: ""`, `Error` has message | ❌ Failure |
| L-03 | Empty LoginId | `{"LoginId":"","Password":"a@3333333333"}` | Error response | ❌ Failure |
| L-04 | Empty Password | `{"LoginId":"DAKS","Password":""}` | Error response | ❌ Failure |
| L-05 | Missing fields | `{}` | Error response | ❌ Failure |
| L-06 | Non-existent user | `{"LoginId":"NONEXIST","Password":"abc"}` | `UniqueId: 0`, Error message | ❌ Failure |
| L-07 | Repeated login | Same creds, 2 calls | Both succeed with **different** RefNo values | ✅ Success |
| L-08 | SQL injection attempt | `{"LoginId":"' OR 1=1 --","Password":"x"}` | Error / rejected (no data leak) | 🔒 Security |

---

### 3.2 OrderEntry

**Endpoint:** `POST /api/PublicAPI/OrderEntry`

**Description:** Places a new order (buy or sell) on the specified exchange. Returns an internal order number (IntOrdNo) on success.

#### Request Schema

| Field | Type | Required | Description | Valid Values |
|-------|------|----------|-------------|-------------|
| `Uniqueid` | int | ✅ | Session UniqueId from login | — |
| `LoginId` | string | ✅ | Username | — |
| `RefNo` | string | ✅ | Session token from login | — |
| `gateway` | string | ✅ | Exchange gateway | `NSECM`, `NSEFO` |
| `Exchange` | string | ✅ | Exchange name | `NSECM`, `NSEFO` |
| `Tokenno` | string | ✅ | Instrument token (exchange-assigned) | e.g., `2885` (RELIANCE) |
| `clientcode` | string | ✅* | Client code (`""` for PRO account) | e.g., `"1A1"` |
| `Buysell` | string | ✅ | Order side | `BUY`, `SELL` |
| `qty` | decimal | ✅ | Order quantity | > 0 |
| `qtydisclosed` | decimal | ✅ | Disclosed quantity | 0 ≤ val ≤ qty |
| `Price` | decimal | ✅ | Order price | > 0 for LIMIT |
| `Triggerprice` | decimal | ⚠️ | Trigger price (required if `Booktype` = `SL`) | > 0 for SL |
| `Booktype` | string | ✅ | Order type | `RL` (Regular/Limit), `SL` (Stop-Loss) |
| `validity` | string | ✅ | Time validity | `DAY`, `IOC`, `FOK` |
| `DeliveryType` | int | ✅ | Delivery mode | `0` = Normal (CNC), `1` = Intraday (MIS) |

> ⚠️ **Note:** Field is `Uniqueid` (lowercase 'i'), NOT `UniqueId` — this is a documented casing inconsistency.

#### Response Schema (OrderResponse)

| Field | Type | Description |
|-------|------|-------------|
| `IntOrdNo` | int | Internal order number (0 on failure) |
| `Error` | string/null | Error text (null/empty on success) |

#### cURL Command

```bash
# BUY 1 share of RELIANCE (Token: 2885) at ₹1 (far from market, won't execute)
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderEntry \
  -H "Content-Type: application/json" \
  -d '{
    "Uniqueid": 29,
    "LoginId": "DAKS",
    "RefNo": "YOUR_REFNO_HERE",
    "gateway": "NSECM",
    "Exchange": "NSECM",
    "Tokenno": "2885",
    "clientcode": "",
    "Buysell": "BUY",
    "qty": 1,
    "qtydisclosed": 0,
    "Price": 1.00,
    "Triggerprice": 0,
    "Booktype": "RL",
    "validity": "DAY",
    "DeliveryType": 0
  }' | jq .
```

#### Edge Cases

- **Expired/invalid RefNo** → Error response, `IntOrdNo: 0`
- **Invalid Tokenno** → Error (instrument not found)
- **Qty = 0 or negative** → Should reject
- **Disclosed qty > total qty** → Should reject
- **SL order without Triggerprice** → Should reject
- **Triggerprice on RL order** → Should be ignored (or set to 0)
- **Invalid gateway** (e.g., `BSECM`) → Error
- **Market closed** → May accept order but remain pending until next session
- **Price = 0 for RL order** → Treated as market order or rejected (verify behavior)

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| OE-01 | Valid BUY limit | BUY, RL, qty=1, Price=1.00, DAY | `IntOrdNo > 0`, Error null | ✅ Success |
| OE-02 | Valid SELL limit | SELL, RL, qty=1, Price=99999, DAY | `IntOrdNo > 0` | ✅ Success |
| OE-03 | Valid SL order | BUY, SL, Triggerprice=100 | `IntOrdNo > 0` | ✅ Success |
| OE-04 | SL without trigger | BUY, SL, Triggerprice=0 | Error, `IntOrdNo: 0` | ❌ Failure |
| OE-05 | Qty = 0 | qty=0 | Error | ❌ Failure |
| OE-06 | Negative qty | qty=-1 | Error | ❌ Failure |
| OE-07 | Disclosed > total | qty=1, qtydisclosed=10 | Error | ❌ Failure |
| OE-08 | Invalid RefNo | RefNo="INVALID" | Error, `IntOrdNo: 0` | ❌ Failure |
| OE-09 | Invalid Tokenno | Tokenno="999999999" | Error | ❌ Failure |
| OE-10 | Invalid exchange | gateway="BSECM" | Error | ❌ Failure |
| OE-11 | IOC validity | validity="IOC" | Accepted (may cancel immediately if no match) | ✅ Success |
| OE-12 | FOK validity | validity="FOK" | Accepted (fills completely or cancels) | ✅ Success |
| OE-13 | Intraday delivery | DeliveryType=1 | Accepted as MIS order | ✅ Success |
| OE-14 | PRO account (empty client) | clientcode="" | Accepted | ✅ Success |

---

### 3.3 OrderStatusRequest

**Endpoint:** `POST /api/PublicAPI/OrderStatusRequest`

**Description:** Returns the current status of an order by its internal order number. Response is a plain string (not JSON object).

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Uniqueid` | int | ✅ | Session UniqueId |
| `RefNo` | string | ✅ | Session token |
| `IntordNo` | int | ✅ | Internal order number from OrderEntry response |

> ⚠️ **Note:** Field is `IntordNo` (lowercase 'o'), NOT `IntOrdNo`.

#### Response

Returns a **plain string** (not wrapped in JSON object):

| Status | Meaning |
|--------|---------|
| `Submitted` | Order submitted to exchange |
| `EPEnding` | Exchange processing pending |
| `Ecancelled` | Cancelled by exchange |
| `ERejected` | Rejected by exchange |
| `MRejected` | Rejected by member/broker |
| `Executed` | Fully executed/filled |
| `""` (empty) | Wrong data provided |

#### cURL Command

```bash
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderStatusRequest \
  -H "Content-Type: application/json" \
  -d '{
    "Uniqueid": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "IntordNo": 12345
  }'
```

#### Edge Cases

- **Non-existent IntordNo** → Returns empty string `""`
- **Wrong UniqueId** → Returns empty string
- **IntordNo from a different session** → May return status or empty (verify)
- **Already cancelled order** → Returns `"Ecancelled"`
- **Partially filled order** → Verify which status is returned

#### Test Cases

| ID | Scenario | Input | Expected | Type |
|----|----------|-------|----------|------|
| OS-01 | Valid pending order | Valid IntordNo | `"Submitted"` or `"EPEnding"` | ✅ Success |
| OS-02 | Executed order | Executed IntordNo | `"Executed"` | ✅ Success |
| OS-03 | Cancelled order | Cancelled IntordNo | `"Ecancelled"` | ✅ Success |
| OS-04 | Non-existent order | IntordNo=0 | `""` (empty string) | ❌ Failure |
| OS-05 | Wrong UniqueId | Uniqueid=0, valid IntordNo | `""` (empty string) | ❌ Failure |
| OS-06 | Invalid RefNo | RefNo="INVALID" | `""` (empty string) | ❌ Failure |

---

### 3.4 ModifyRequest

**Endpoint:** `POST /api/PublicAPI/ModifyRequest`

**Description:** Modifies an existing pending order's price, quantity, type, or validity.

#### Request Schema

| Field | Type | Required | Description | Valid Values |
|-------|------|----------|-------------|-------------|
| `Uniqueid` | int | ✅ | Session UniqueId | — |
| `RefNo` | string | ✅ | Session token | — |
| `IntordNo` | int | ✅ | Order to modify | — |
| `qty` | decimal | ✅ | New quantity | > 0 |
| `qtydisclosed` | decimal | ✅ | New disclosed quantity | 0 ≤ val ≤ qty |
| `Price` | decimal | ✅ | New price | > 0 |
| `TriggerPrice` | decimal | ✅ | New trigger price | Required if Booktype=SL |
| `Booktype` | string | ✅ | New book type | `RL`, `SL` |
| `Validity` | string | ✅ | New validity | `DAY`, `IOC`, `FOK` |

> ⚠️ **Note:** `IntordNo` (lowercase 'o') and `TriggerPrice` (capital T and P — different from OrderEntry's `Triggerprice`).

#### Response Schema (OrderResponse)

| Field | Type | Description |
|-------|------|-------------|
| `IntOrdNo` | int | Modified order number (0 on failure) |
| `Error` | string/null | Error text |

#### cURL Command

```bash
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/ModifyRequest \
  -H "Content-Type: application/json" \
  -d '{
    "Uniqueid": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "IntordNo": 12345,
    "qty": 1,
    "qtydisclosed": 0,
    "Price": 2.00,
    "TriggerPrice": 0,
    "Booktype": "RL",
    "Validity": "DAY"
  }' | jq .
```

#### Edge Cases

- **Modifying executed order** → Error (already filled)
- **Modifying cancelled order** → Error
- **Changing RL → SL without TriggerPrice** → Should error
- **Changing SL → RL** → TriggerPrice should be ignored/zeroed
- **Qty less than already traded qty** → Should error
- **Invalid IntordNo** → Error, `IntOrdNo: 0`

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| MR-01 | Modify price of pending order | Price=2.00 | `IntOrdNo > 0`, Error null | ✅ Success |
| MR-02 | Modify qty of pending order | qty=2 | `IntOrdNo > 0` | ✅ Success |
| MR-03 | Change RL to SL with trigger | Booktype=SL, TriggerPrice=100 | `IntOrdNo > 0` | ✅ Success |
| MR-04 | Change RL to SL without trigger | Booktype=SL, TriggerPrice=0 | Error | ❌ Failure |
| MR-05 | Modify executed order | IntordNo of executed order | Error | ❌ Failure |
| MR-06 | Modify cancelled order | IntordNo of cancelled order | Error | ❌ Failure |
| MR-07 | Invalid IntordNo | IntordNo=0 | Error | ❌ Failure |
| MR-08 | Change validity to IOC | Validity="IOC" | Accepted | ✅ Success |

---

### 3.5 CancelRequest

**Endpoint:** `POST /api/PublicAPI/CancelRequest`

**Description:** Cancels an existing pending order by its internal order number.

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `UniqueId` | int | ✅ | Session UniqueId |
| `RefNo` | string | ✅ | Session token |
| `IntOrdNo` | int | ✅ | Order to cancel |

> ⚠️ **Note:** This endpoint uses `UniqueId` (capital 'I') and `IntOrdNo` (capital 'O') — different casing from OrderEntry/Modify.

#### Response Schema (OrderResponse)

| Field | Type | Description |
|-------|------|-------------|
| `IntOrdNo` | int | Cancelled order number (0 on failure) |
| `Error` | string/null | Error text |

#### cURL Command

```bash
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/CancelRequest \
  -H "Content-Type: application/json" \
  -d '{
    "UniqueId": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "IntOrdNo": 12345
  }' | jq .
```

#### Edge Cases

- **Cancel already cancelled order** → Error
- **Cancel executed order** → Error (already filled)
- **Cancel non-existent order** → Error
- **Cancel with wrong RefNo** → Error
- **Double cancel (race condition)** → First succeeds, second fails

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| CR-01 | Cancel pending order | Valid IntOrdNo | `IntOrdNo > 0`, Error null | ✅ Success |
| CR-02 | Cancel already cancelled | Same IntOrdNo again | Error | ❌ Failure |
| CR-03 | Cancel executed order | IntOrdNo of filled order | Error | ❌ Failure |
| CR-04 | Cancel non-existent | IntOrdNo=0 | Error | ❌ Failure |
| CR-05 | Invalid RefNo | RefNo="INVALID" | Error | ❌ Failure |

---

### 3.6 OrderBookRequest

**Endpoint:** `POST /api/PublicAPI/OrderBookRequest`

**Description:** Retrieves all orders placed today. Optionally filter by IntOrdNo or TokenNo for specific orders/instruments.

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `UniqueId` | int | ✅ | Session UniqueId |
| `RefNo` | string | ✅ | Session token |
| `Error` | string | ✅ | Error text (send empty `""`) |
| `IntOrdNo` | int | ❌ | Filter by specific order number |
| `TokenNo` | string | ❌ | Filter by instrument token |
| `ExchOrdNo` | string | ❌ | Not required (returned in response) |
| `QtyRemaining` | decimal | ❌ | Not required (returned in response) |
| `QtyTraded` | decimal | ❌ | Not required (returned in response) |
| `OrderStatus` | string | ❌ | Not required (returned in response) |
| `OrderPrice` | decimal | ❌ | Not required (returned in response) |
| `OrderTime` | datetime | ❌ | Not required (returned in response) |
| `BuySell` | string | ❌ | Not required (returned in response) |
| `TriggerPrice` | decimal | ❌ | Not required (returned in response) |

#### Response

Returns a **collection (array)** of order records with all fields populated.

#### cURL Commands

```bash
# Get ALL orders today
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderBookRequest \
  -H "Content-Type: application/json" \
  -d '{
    "UniqueId": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "Error": ""
  }' | jq .
```

```bash
# Filter by specific order number
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderBookRequest \
  -H "Content-Type: application/json" \
  -d '{
    "UniqueId": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "Error": "",
    "IntOrdNo": 12345
  }' | jq .
```

```bash
# Filter by instrument token
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderBookRequest \
  -H "Content-Type: application/json" \
  -d '{
    "UniqueId": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "Error": "",
    "TokenNo": "2885"
  }' | jq .
```

#### Edge Cases

- **No orders today** → Empty array `[]`
- **Filter by non-existent IntOrdNo** → Empty array
- **Filter by non-existent TokenNo** → Empty array
- **Invalid RefNo** → Error response
- **Orders from previous days** → Not returned (today's orders only)

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| OB-01 | Get all orders | No filters | Array of today's orders | ✅ Success |
| OB-02 | Filter by IntOrdNo | IntOrdNo=known | Single order in array | ✅ Success |
| OB-03 | Filter by TokenNo | TokenNo="2885" | Orders for RELIANCE | ✅ Success |
| OB-04 | No orders today | Fresh account | Empty array `[]` | ✅ Success |
| OB-05 | Invalid RefNo | RefNo="INVALID" | Error | ❌ Failure |
| OB-06 | Non-existent IntOrdNo | IntOrdNo=999999 | Empty array | ✅ Success |

---

### 3.7 TradeBookRequest

**Endpoint:** `POST /api/PublicAPI/TradeBookRequest`

**Description:** Retrieves all executed trades for today. Optionally filter by IntOrdNo or TokenNo.

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `UniqueId` | int | ✅ | Session UniqueId |
| `RefNo` | string | ✅ | Session token |
| `Error` | string | ✅ | Error text (send empty `""`) |
| `IntOrdNo` | int | ❌ | Filter by order number |
| `TokenNo` | string | ❌ | Filter by instrument |
| `QtyTraded` | decimal | ❌ | Not required (returned in response) |
| `TradePrice` | decimal | ❌ | Not required (returned in response) |
| `TradeTime` | datetime | ❌ | Not required (returned in response) |
| `ExchOrdNo` | string | ❌ | Not required (returned in response) |
| `TradeNo` | string | ❌ | Not required (returned in response) |
| `BuySell` | string | ❌ | Not required (returned in response) |

#### Response

Returns a **collection (array)** of trade records.

#### cURL Command

```bash
# Get ALL trades today
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/TradeBookRequest \
  -H "Content-Type: application/json" \
  -d '{
    "UniqueId": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "Error": ""
  }' | jq .
```

#### Edge Cases

- **No trades today** → Empty array
- **Partially filled order** → Trade records for filled portion only
- **Same order filled in multiple lots** → Multiple trade records for same IntOrdNo

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| TB-01 | Get all trades | No filters | Array of today's trades | ✅ Success |
| TB-02 | Filter by IntOrdNo | IntOrdNo=known executed order | Trade records for that order | ✅ Success |
| TB-03 | No trades today | Fresh account | Empty array `[]` | ✅ Success |
| TB-04 | Invalid RefNo | RefNo="INVALID" | Error | ❌ Failure |

---

### 3.8 PositionRequest

**Endpoint:** `POST /api/PublicAPI/PositionRequest`

**Description:** Retrieves current open positions. Optionally filter by TokenNo.

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Uniqueid` | int | ✅ | Session UniqueId |
| `RefNo` | string | ✅ | Session token |
| `Error` | string | ✅ | Error text (send empty `""`) |
| `TokenNo` | string | ❌ | Filter by instrument |
| `ClientCode` | string | ✅* | Client code (`""` for PRO account) |
| `Qty` | decimal | ❌ | Not required (returned in response) |
| `Average` | decimal | ❌ | Not required (returned in response) |

> ⚠️ **Note:** Uses `Uniqueid` (lowercase 'i') — same as OrderEntry.

#### Response

Returns a **collection (array)** of position records.

#### cURL Command

```bash
# Get ALL positions
curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/PositionRequest \
  -H "Content-Type: application/json" \
  -d '{
    "Uniqueid": 29,
    "RefNo": "YOUR_REFNO_HERE",
    "Error": "",
    "ClientCode": ""
  }' | jq .
```

#### Edge Cases

- **No positions** → Empty array
- **PRO account** → Send `ClientCode: ""`
- **Client account** → Send actual client code (e.g., `"1A1"`)
- **Wrong ClientCode** → May return empty or error
- **Positions from expired contracts** → Verify behavior

#### Test Cases

| ID | Scenario | Key Input | Expected | Type |
|----|----------|-----------|----------|------|
| PR-01 | Get all positions | No filters, PRO account | Array of positions | ✅ Success |
| PR-02 | Filter by TokenNo | TokenNo="2885" | RELIANCE position only | ✅ Success |
| PR-03 | No positions | Fresh account | Empty array `[]` | ✅ Success |
| PR-04 | Invalid RefNo | RefNo="INVALID" | Error | ❌ Failure |
| PR-05 | Wrong ClientCode | ClientCode="WRONG" | Empty or error | ❌ Failure |

---

## 4. WebSocket Data Feed API

> **UAT Endpoint:** `ws://115.242.15.134:19101`
> **Live Endpoint:** `wss://feedapi.com`
> **Protocol:** WebSocket with JSON messages
> **Heartbeat:** Send `Info` packet with `InfoType="HB"` every 60 seconds

### General Packet Structure

All WebSocket messages follow this wrapper:

```json
{
  "Type": "<MessageType>",
  "Data": <object or string>
}
```

---

### 4.1 Login / Logout

#### Login Request

```json
{
  "Type": "Login",
  "Data": {
    "LoginId": "DAKS",
    "Password": "a@3333333333"
  }
}
```

#### Login Response (Success)

```json
{
  "Type": "Login",
  "Data": {
    "Error": "",
    "LoginId": "DAKS",
    "Version": "1.1",
    "Xchgs": "NSECM,NSEFO,BSECM,BSEFO"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `Error` | string | Empty on success, error message on failure |
| `LoginId` | string | Echoed back LoginId |
| `Version` | string | API version |
| `Xchgs` | string | Comma-separated allowed exchanges |

#### Login Response (Failure)

```json
{
  "Type": "Login",
  "Data": {
    "Error": "Invalid credentials",
    "LoginId": "",
    "Version": "",
    "Xchgs": ""
  }
}
```

#### Logout Request

```json
{
  "Type": "Logout",
  "Data": "logout"
}
```

#### Logout Response

```json
{
  "Type": "Logout",
  "Data": "Logged out successfully"
}
```

#### wscat Test

```bash
# Connect to UAT
wscat -c ws://115.242.15.134:19101

# After connected, send login:
{"Type":"Login","Data":{"LoginId":"DAKS","Password":"a@3333333333"}}

# Logout:
{"Type":"Logout","Data":"logout"}
```

#### Test Cases

| ID | Scenario | Input | Expected | Type |
|----|----------|-------|----------|------|
| WL-01 | Valid login | Valid LoginId/Password | Error="", Xchgs populated | ✅ Success |
| WL-02 | Wrong password | Invalid password | Error has message | ❌ Failure |
| WL-03 | Empty credentials | LoginId="" | Error | ❌ Failure |
| WL-04 | Logout after login | Logout message | Clean disconnect | ✅ Success |
| WL-05 | Logout without login | Logout before login | Error or disconnect | ❌ Failure |

---

### 4.2 TokenRequest

**Direction:** Client → Server (Subscribe/Unsubscribe to instruments)

#### Request Structure

```json
{
  "Type": "TokenRequest",
  "Data": {
    "SubType": true,
    "FeedType": 1,
    "quotes": [
      {
        "Xchg": "NSECM",
        "Tkn": "2885",
        "Symbol": "RELIANCE"
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `SubType` | boolean | `true` = Subscribe, `false` = Unsubscribe |
| `FeedType` | int | `1` = MarketData, `2` = Depth, `3` = SnapQuote, `4` = Greeks |
| `quotes` | array | Array of instruments |
| `quotes[].Xchg` | string | Exchange: `NSECM`, `NSEFO`, `BSECM`, `BSEFO` |
| `quotes[].Tkn` | string | Token number (exchange instrument ID) |
| `quotes[].Symbol` | string | Symbol name |

#### Subscribe Examples

```json
// Subscribe to MarketData for RELIANCE
{
  "Type": "TokenRequest",
  "Data": {
    "SubType": true,
    "FeedType": 1,
    "quotes": [{"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}]
  }
}
```

```json
// Subscribe to Depth for NIFTY futures
{
  "Type": "TokenRequest",
  "Data": {
    "SubType": true,
    "FeedType": 2,
    "quotes": [{"Xchg": "NSEFO", "Tkn": "57133", "Symbol": "NIFTY"}]
  }
}
```

```json
// Subscribe to Greeks for options
{
  "Type": "TokenRequest",
  "Data": {
    "SubType": true,
    "FeedType": 4,
    "quotes": [{"Xchg": "NSEFO", "Tkn": "57134", "Symbol": "NIFTY24000CE"}]
  }
}
```

#### Unsubscribe

```json
{
  "Type": "TokenRequest",
  "Data": {
    "SubType": false,
    "FeedType": 1,
    "quotes": [{"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}]
  }
}
```

#### Test Cases

| ID | Scenario | Input | Expected | Type |
|----|----------|-------|----------|------|
| TR-01 | Subscribe MarketData | FeedType=1, RELIANCE | MarketData messages start | ✅ Success |
| TR-02 | Subscribe Depth | FeedType=2 | Depth messages with 5 levels | ✅ Success |
| TR-03 | Subscribe Greeks | FeedType=4, options token | Greek messages with IV, Delta etc. | ✅ Success |
| TR-04 | Unsubscribe | SubType=false | Messages stop for that token | ✅ Success |
| TR-05 | Invalid token | Tkn="9999999" | No data or error Info message | ❌ Failure |
| TR-06 | Multiple tokens | 5+ tokens in quotes array | All subscribed | ✅ Success |
| TR-07 | Subscribe before login | TokenRequest without login | Error | ❌ Failure |

---

### 4.3 MarketData Response

**Type:** `MarketData` (received after subscribing with FeedType=1)

```json
{
  "Type": "MarketData",
  "Data": {
    "Xchg": "NSECM",
    "Tkn": "2885",
    "LTP": 2450.50,
    "LTQ": 10.00,
    "LUT": "14:30:15",
    "LTT": "14:30:14",
    "ATP": 2448.75,
    "BQ": 100.00,
    "BP": 2450.00,
    "SQ": 50.00,
    "SP": 2451.00,
    "TBQ": 125000.00,
    "TSQ": 98000.00,
    "TTQ": 5000000.00,
    "TTV": 12250000000.00,
    "OI": 0.00,
    "O": 2440.00,
    "H": 2465.00,
    "L": 2435.00,
    "C": 2442.00,
    "DPRL": 2197.80,
    "DPRH": 2686.20
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `Xchg` | string | Exchange name |
| `Tkn` | string | Token number |
| `LTP` | decimal | Last Traded Price |
| `LTQ` | decimal | Last Traded Quantity |
| `LUT` | string | Last Update Time (HH:mm:ss) |
| `LTT` | string | Last Trade Time (HH:mm:ss) |
| `ATP` | decimal | Average Trade Price |
| `BQ` | decimal | Best Bid Quantity |
| `BP` | decimal | Best Bid Price |
| `SQ` | decimal | Best Ask Quantity |
| `SP` | decimal | Best Ask Price |
| `TBQ` | decimal | Total Bid Quantity |
| `TSQ` | decimal | Total Ask Quantity |
| `TTQ` | decimal | Total Traded Quantity (Volume) |
| `TTV` | decimal | Total Traded Value |
| `OI` | decimal | Open Interest (0 for equity) |
| `O` | decimal | Open Price |
| `H` | decimal | High Price |
| `L` | decimal | Low Price |
| `C` | decimal | Previous Close Price |
| `DPRL` | decimal | Daily Price Range Low (circuit limit) |
| `DPRH` | decimal | Daily Price Range High (circuit limit) |

#### Edge Cases

- **Pre-market hours** → LTP may be 0 or previous close
- **OI = 0** for cash market instruments (normal)
- **LUT vs LTT** → LUT is update time, LTT is trade time (can differ)
- **Weekend/Holiday** → No data (connection stays alive with heartbeat)

---

### 4.4 Depth Response

**Type:** `Depth` (received after subscribing with FeedType=2)

```json
{
  "Type": "Depth",
  "Data": {
    "Xchg": "NSECM",
    "Tkn": "2885",
    "Depths": [
      {"BO": 5, "BP": 2450.00, "BQ": 100, "SQ": 50, "SP": 2451.00, "SO": 3},
      {"BO": 8, "BP": 2449.50, "BQ": 200, "SQ": 75, "SP": 2451.50, "SO": 4},
      {"BO": 12, "BP": 2449.00, "BQ": 350, "SQ": 120, "SP": 2452.00, "SO": 7},
      {"BO": 6, "BP": 2448.50, "BQ": 180, "SQ": 90, "SP": 2452.50, "SO": 5},
      {"BO": 10, "BP": 2448.00, "BQ": 500, "SQ": 200, "SP": 2453.00, "SO": 8}
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `BO` | decimal | Number of Bid Orders |
| `BP` | decimal | Bid Price |
| `BQ` | decimal | Bid Quantity |
| `SQ` | decimal | Ask Quantity |
| `SP` | decimal | Ask Price |
| `SO` | decimal | Number of Ask Orders |

> **Note:** 5 levels of depth (index 0 = best bid/ask)

#### Edge Cases

- **Illiquid instrument** → Fewer than 5 levels, some may be 0
- **Pre-market** → Depth may be empty or stale
- **Depths array size** → Always 5 entries, but values may be 0

---

### 4.5 Greek Response

**Type:** `Greek` (received after subscribing with FeedType=4)

Contains all MarketData fields **plus** Greeks and Depth:

```json
{
  "Type": "Greek",
  "Data": {
    "Xchg": "NSEFO",
    "Tkn": "57134",
    "Symbol": "NIFTY24000CE",
    "LTP": 150.00,
    "LTQ": 50,
    "LUT": "14:30:15",
    "LTT": "14:30:14",
    "ATP": 148.50,
    "BQ": 100, "BP": 149.50,
    "SQ": 75, "SP": 150.50,
    "TBQ": 50000, "TSQ": 45000,
    "TTQ": 200000, "TTV": 30000000,
    "OI": 1500000,
    "O": 145.00, "H": 155.00, "L": 142.00, "C": 143.50,
    "DPRL": 0.05, "DPRH": 500.00,
    "SpotPrice": 24150.00,
    "IV": 12.50,
    "Delta": 0.55,
    "Gamma": 0.0025,
    "Theta": -8.50,
    "Vega": 15.20,
    "Rho": 3.10,
    "Depths": [
      {"BO": 5, "BP": 149.50, "BQ": 100, "SQ": 75, "SP": 150.50, "SO": 3}
    ]
  }
}
```

**Additional fields beyond MarketData:**

| Field | Type | Description |
|-------|------|-------------|
| `Symbol` | string | Full symbol description |
| `SpotPrice` | decimal | Underlying spot price |
| `IV` | decimal | Implied Volatility |
| `Delta` | decimal | Option Delta |
| `Gamma` | decimal | Option Gamma |
| `Theta` | decimal | Option Theta |
| `Vega` | decimal | Option Vega |
| `Rho` | decimal | Option Rho |
| `Depths` | array | Depth levels (same structure as Depth response) |

#### Edge Cases

- **Deep OTM options** → Delta near 0, IV may be very high
- **Expired options** → No data or zero values
- **Non-option tokens** → Greeks may be 0/empty

---

### 4.6 IndexData Response

**Type:** `IndexData` (automatically received after login for subscribed exchanges)

```json
{
  "Type": "IndexData",
  "Data": [
    {"Symbol": "NIFTY50", "Price": 24150.00, "O": 24100.00, "H": 24200.00, "L": 24050.00, "C": 24080.00},
    {"Symbol": "SENSEX", "Price": 79500.00, "O": 79300.00, "H": 79600.00, "L": 79200.00, "C": 79350.00}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `Symbol` | string | Index name (NIFTY50, SENSEX, etc.) |
| `Price` | decimal | Current index value |
| `O` | decimal | Today's open |
| `H` | decimal | Today's high |
| `L` | decimal | Today's low |
| `C` | decimal | Previous close |

> **Note:** `Data` is an **array** (not a single object), unlike other message types.

---

### 4.7 OChain (Option Chain)

#### Request

```json
{
  "Type": "OChain",
  "Data": {
    "SubType": true,
    "Xchg": "NSEFO",
    "Symbol": "NIFTY",
    "Expiry": "03-07-2025"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `SubType` | boolean | `true` = Subscribe, `false` = Unsubscribe |
| `Xchg` | string | Exchange (`NSEFO`, `BSEFO`) |
| `Symbol` | string | Underlying (NIFTY, BANKNIFTY, SENSEX) |
| `Expiry` | string | Expiry date (`DD-MM-YYYY`) |

#### Response (Summary Level)

| Field | Type | Description |
|-------|------|-------------|
| `SpotPrice` | decimal | Live underlying price |
| `VIX` | decimal | India VIX |
| `MaxPain` | decimal | Max Pain strike |
| `CallVolTot` | decimal | Total call volume |
| `PutVolTot` | decimal | Total put volume |
| `CEIVTotal` | decimal | Total CE implied volatility |
| `PEIVTotal` | decimal | Total PE implied volatility |
| `IVSkew` | decimal | PE IV Total - CE IV Total |
| `CEOITot` | decimal | Total call open interest |
| `PEOITot` | decimal | Total put open interest |
| `PCR` | decimal | Put/Call OI Ratio |
| `OptChain` | array | Array of strike-level data |

#### Response (Strike Level — 50+ fields per strike)

Each entry in `OptChain[]` contains CE and PE data:

**Call side fields:** `CETkn`, `CLTP`, `CBidQ`, `CBidP`, `CAskP`, `CAskQ`, `COI`, `CVol`, `CBuyer`, `CSeller`, `CHVNBids`, `CHVNBidPrice`, `CHVNAsks`, `CHVNAskPrice`, `CIV`, `CTheta`, `CDelta`, `CGamma`, `CVega`, `CEVWAP`, `CEAncVWAP`, `CETrendScore`, `CEPremDivergance`

**Put side fields:** `PETkn`, `PLTP`, `PBidQ`, `PBid`, `PAsk`, `PAskQ`, `POI`, `PVol`, `PBuyer`, `PSeller`, `PHVNBids`, `PHVNBidPrice`, `PHVNAsks`, `PHVNAskPrice`, `PIV`, `PTheta`, `PDelta`, `PGamma`, `PVega`, `PEVWAP`, `PEAncVWAP`, `PETrendScore`, `PEPremDivergance`

**Common:** `Strike`, `OIPCR`, `IVSkew`

#### Test Cases

| ID | Scenario | Input | Expected | Type |
|----|----------|-------|----------|------|
| OC-01 | Subscribe NIFTY chain | Symbol=NIFTY, valid expiry | OChain data with strikes | ✅ Success |
| OC-02 | Invalid expiry | Expiry="99-99-9999" | Error or empty | ❌ Failure |
| OC-03 | Unsubscribe | SubType=false | OChain updates stop | ✅ Success |
| OC-04 | Non-options exchange | Xchg="NSECM" | Error or empty | ❌ Failure |

---

### 4.8 CandleBar Response

**Type:** `CandleBar`

```json
{
  "Type": "CandleBar",
  "Data": {
    "Xchg": "NSEFO",
    "Symbol": "NIFTY",
    "Expiry": "03-07-2025",
    "VIX": 14.50,
    "ohlcBars": [
      {
        "O": 24100.00,
        "H": 24150.00,
        "L": 24090.00,
        "C": "24130.00",
        "Vol": 500000,
        "Time": "09:15",
        "OI": 1200000,
        "OIChng": 50000,
        "VWAP": 24120.50,
        "AncVWAP": 24115.00,
        "CVD": -25000
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `O` | decimal | Bar open |
| `H` | decimal | Bar high |
| `L` | decimal | Bar low |
| `C` | string | Bar close (note: **string**, not decimal) |
| `Vol` | decimal | Volume in this bar |
| `Time` | string | Bar time (HH:mm) |
| `OI` | decimal | OI at bar close |
| `OIChng` | decimal | OI change from previous bar |
| `VWAP` | decimal | VWAP at this bar |
| `AncVWAP` | decimal | Anchor VWAP |
| `CVD` | decimal | Cumulative Volume Delta (Seller - Buyer) |

> ⚠️ **Note:** Close (`C`) is a **string** type in the docs, not decimal. Handle accordingly.

---

### 4.9 FeedStatus / Info

#### FeedStatus (Exchange connection status)

```json
{
  "Type": "FeedStatus",
  "Data": [
    {"Xchg": "NSECM", "Status": 1},
    {"Xchg": "NSEFO", "Status": 1},
    {"Xchg": "BSECM", "Status": 0}
  ]
}
```

| Status | Meaning |
|--------|---------|
| `1` | Connected |
| `0` | Disconnected |

#### Info (Informational messages)

```json
{
  "Type": "Info",
  "Data": {
    "InfoType": "HB",
    "InfoMsg": "Heartbeat"
  }
}
```

| InfoType | Purpose |
|----------|---------|
| `Error` | Error message |
| `Warning` | Warning message |
| `XchgMsg` | Exchange broadcast message |
| `BrkMsg` | Broker message |
| `HB` | Heartbeat |

#### Heartbeat (CRITICAL — must send every 60 seconds)

```json
{"Type":"Info","Data":{"InfoType":"HB","InfoMsg":""}}
```

> **If no heartbeat is sent for ~60 seconds and there's no other client activity, the server will disconnect the WebSocket.**

#### Test Cases

| ID | Scenario | Action | Expected | Type |
|----|----------|--------|----------|------|
| FS-01 | Check feed status | Login and wait | FeedStatus with connected exchanges | ✅ Success |
| HB-01 | Send heartbeat | Send HB packet | Connection stays alive | ✅ Success |
| HB-02 | No heartbeat for 2min | Don't send HB, no subscriptions | Connection drops | ❌ Failure |

---

### WebSocket Complete Test Script (Node.js)

```javascript
const WebSocket = require('ws');

const WS_URL = 'ws://115.242.15.134:19101'; // UAT
const LOGIN_ID = 'DAKS';
const PASSWORD = 'a@3333333333';

let ws;
let heartbeatInterval;

function connect() {
  ws = new WebSocket(WS_URL);

  ws.on('open', () => {
    console.log('[CONNECTED]');
    // Step 1: Login
    const loginMsg = JSON.stringify({
      Type: 'Login',
      Data: { LoginId: LOGIN_ID, Password: PASSWORD }
    });
    ws.send(loginMsg);
    console.log('[SENT] Login');
  });

  ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    console.log(`[RECV] Type=${msg.Type}`, JSON.stringify(msg.Data).substring(0, 200));

    if (msg.Type === 'Login' && msg.Data.Error === '') {
      console.log('[LOGIN SUCCESS] Exchanges:', msg.Data.Xchgs);

      // Step 2: Start heartbeat
      heartbeatInterval = setInterval(() => {
        ws.send(JSON.stringify({ Type: 'Info', Data: { InfoType: 'HB', InfoMsg: '' } }));
        console.log('[SENT] Heartbeat');
      }, 55000); // every 55 seconds (buffer before 60s timeout)

      // Step 3: Subscribe to MarketData
      ws.send(JSON.stringify({
        Type: 'TokenRequest',
        Data: {
          SubType: true,
          FeedType: 1,
          quotes: [
            { Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' },
            { Xchg: 'NSECM', Tkn: '11536', Symbol: 'TCS' }
          ]
        }
      }));
      console.log('[SENT] Subscribe MarketData: RELIANCE, TCS');

      // Step 4: Subscribe to Depth (after 2s)
      setTimeout(() => {
        ws.send(JSON.stringify({
          Type: 'TokenRequest',
          Data: {
            SubType: true,
            FeedType: 2,
            quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }]
          }
        }));
        console.log('[SENT] Subscribe Depth: RELIANCE');
      }, 2000);

      // Step 5: Unsubscribe after 30s
      setTimeout(() => {
        ws.send(JSON.stringify({
          Type: 'TokenRequest',
          Data: {
            SubType: false,
            FeedType: 1,
            quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }]
          }
        }));
        console.log('[SENT] Unsubscribe RELIANCE MarketData');
      }, 30000);

      // Step 6: Logout after 60s
      setTimeout(() => {
        clearInterval(heartbeatInterval);
        ws.send(JSON.stringify({ Type: 'Logout', Data: 'logout' }));
        console.log('[SENT] Logout');
      }, 60000);
    }
  });

  ws.on('close', () => {
    console.log('[DISCONNECTED]');
    clearInterval(heartbeatInterval);
  });

  ws.on('error', (err) => {
    console.error('[ERROR]', err.message);
  });
}

connect();
```

### WebSocket Test Script (Python)

```python
import asyncio
import json
import websockets

WS_URL = "ws://115.242.15.134:19101"  # UAT
LOGIN_ID = "DAKS"
PASSWORD = "a@3333333333"

async def test_feed():
    async with websockets.connect(WS_URL) as ws:
        # Login
        await ws.send(json.dumps({
            "Type": "Login",
            "Data": {"LoginId": LOGIN_ID, "Password": PASSWORD}
        }))
        resp = json.loads(await ws.recv())
        print(f"Login: {resp}")

        if resp["Data"]["Error"] == "":
            print(f"Exchanges: {resp['Data']['Xchgs']}")

            # Subscribe MarketData
            await ws.send(json.dumps({
                "Type": "TokenRequest",
                "Data": {
                    "SubType": True,
                    "FeedType": 1,
                    "quotes": [{"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}]
                }
            }))

            # Read 10 messages
            for i in range(10):
                msg = json.loads(await ws.recv())
                print(f"[{i+1}] Type={msg['Type']}: {json.dumps(msg['Data'])[:150]}")

            # Heartbeat
            await ws.send(json.dumps({
                "Type": "Info",
                "Data": {"InfoType": "HB", "InfoMsg": ""}
            }))
            print("Heartbeat sent")

            # Unsubscribe
            await ws.send(json.dumps({
                "Type": "TokenRequest",
                "Data": {
                    "SubType": False,
                    "FeedType": 1,
                    "quotes": [{"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}]
                }
            }))

            # Logout
            await ws.send(json.dumps({"Type": "Logout", "Data": "logout"}))
            print("Logged out")

asyncio.run(test_feed())
```

---

## 5. End-to-End Test Scenarios

### Scenario 1: Full Order Lifecycle

```
Login → Place Order → Check Status → Modify → Cancel → Verify in OrderBook
```

```bash
# Step 1: Login
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/LoginRequest \
  -H "Content-Type: application/json" \
  -d '{"LoginId":"DAKS","Password":"a@3333333333"}')
echo "Login: $RESP"

UNIQUE_ID=$(echo $RESP | jq -r '.UniqueId')
REF_NO=$(echo $RESP | jq -r '.RefNo')

# Step 2: Place order (BUY RELIANCE at ₹1 — won't execute)
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderEntry \
  -H "Content-Type: application/json" \
  -d "{
    \"Uniqueid\": $UNIQUE_ID,
    \"LoginId\": \"DAKS\",
    \"RefNo\": \"$REF_NO\",
    \"gateway\": \"NSECM\",
    \"Exchange\": \"NSECM\",
    \"Tokenno\": \"2885\",
    \"clientcode\": \"\",
    \"Buysell\": \"BUY\",
    \"qty\": 1,
    \"qtydisclosed\": 0,
    \"Price\": 1.00,
    \"Triggerprice\": 0,
    \"Booktype\": \"RL\",
    \"validity\": \"DAY\",
    \"DeliveryType\": 0
  }")
echo "OrderEntry: $RESP"

INT_ORD_NO=$(echo $RESP | jq -r '.IntOrdNo')

# Step 3: Check status
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderStatusRequest \
  -H "Content-Type: application/json" \
  -d "{
    \"Uniqueid\": $UNIQUE_ID,
    \"RefNo\": \"$REF_NO\",
    \"IntordNo\": $INT_ORD_NO
  }")
echo "Status: $RESP"

# Step 4: Modify price to ₹2
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/ModifyRequest \
  -H "Content-Type: application/json" \
  -d "{
    \"Uniqueid\": $UNIQUE_ID,
    \"RefNo\": \"$REF_NO\",
    \"IntordNo\": $INT_ORD_NO,
    \"qty\": 1,
    \"qtydisclosed\": 0,
    \"Price\": 2.00,
    \"TriggerPrice\": 0,
    \"Booktype\": \"RL\",
    \"Validity\": \"DAY\"
  }")
echo "Modify: $RESP"

# Step 5: Cancel
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/CancelRequest \
  -H "Content-Type: application/json" \
  -d "{
    \"UniqueId\": $UNIQUE_ID,
    \"RefNo\": \"$REF_NO\",
    \"IntOrdNo\": $INT_ORD_NO
  }")
echo "Cancel: $RESP"

# Step 6: Verify in OrderBook
RESP=$(curl -s -X POST http://192.168.6.164:16006/api/PublicAPI/OrderBookRequest \
  -H "Content-Type: application/json" \
  -d "{
    \"UniqueId\": $UNIQUE_ID,
    \"RefNo\": \"$REF_NO\",
    \"Error\": \"\",
    \"IntOrdNo\": $INT_ORD_NO
  }")
echo "OrderBook: $RESP"
```

### Scenario 2: Authentication Edge Cases

| Test | Action | Expected |
|------|--------|----------|
| Wrong password | Login with bad password | UniqueId=0, RefNo="" |
| Use old RefNo | Login again (new RefNo), use old RefNo | May still work (both sessions valid) or error |
| Concurrent sessions | Login twice simultaneously | Both get different valid RefNo |
| Session persistence | Login, wait 4+ hours, call OrderBook | Verify if session expired |

### Scenario 3: WebSocket Resilience

| Test | Action | Expected |
|------|--------|----------|
| Reconnect | Close WebSocket, reconnect, re-login | New session, need to re-subscribe |
| Heartbeat timeout | Connect, login, subscribe, wait 2 min without HB | Disconnected |
| Rapid subscribe/unsub | Subscribe then immediately unsubscribe 100 times | No crash, clean state |
| Max subscriptions | Subscribe to 1000+ tokens | Verify limit or degradation |

---

## 6. Common Issues & Troubleshooting

### Issue 1: RefNo Expires / Changes

**Symptom:** API calls return errors after working previously.
**Cause:** Each `LoginRequest` generates a NEW `RefNo`. If you logged in again elsewhere, the old RefNo may be invalidated server-side.
**Fix:** Always use the RefNo from your most recent login.

### Issue 2: Field Name Casing

**Symptom:** API returns unexpected errors or ignores fields.
**Cause:** The API has inconsistent field name casing across endpoints (see Section 7).
**Fix:** Use the EXACT casing documented per endpoint. When in doubt, test with both casings.

### Issue 3: SL Order Rejected

**Symptom:** Stop-loss order returns error.
**Cause:** `Booktype: "SL"` requires a valid `Triggerprice > 0`.
**Fix:** Always set `Triggerprice` (or `TriggerPrice` for Modify) when using SL booktype.

### Issue 4: PRO vs Client Account

**Symptom:** Position/Order requests return empty for client accounts.
**Cause:** `clientcode` must match the actual client code.
**Fix:** For PRO accounts, send `clientcode: ""`. For client accounts, send the actual code (e.g., `"1A1"`).

### Issue 5: WebSocket Disconnects Randomly

**Symptom:** WebSocket connection drops after ~60 seconds of inactivity.
**Cause:** Server requires heartbeat.
**Fix:** Send `{"Type":"Info","Data":{"InfoType":"HB","InfoMsg":""}}` every 55 seconds.

### Issue 6: OrderStatus Returns Empty String

**Symptom:** OrderStatusRequest returns `""`.
**Cause:** Invalid `IntordNo`, wrong `Uniqueid`, or wrong `RefNo`.
**Fix:** Verify all three fields match the session that placed the order.

### Issue 7: Gateway vs Exchange Confusion

**Symptom:** Order rejected with exchange-related error.
**Cause:** `gateway` and `Exchange` often have the same value but serve different purposes.
**Fix:** For NSE Cash: `gateway: "NSECM", Exchange: "NSECM"`. For NSE F&O: `gateway: "NSEFO", Exchange: "NSEFO"`.

### Issue 8: Decimal vs Integer Types

**Symptom:** API rejects quantity or price values.
**Cause:** `qty` and `Price` are declared as `Decimal` in the API spec.
**Fix:** Send decimal values (e.g., `1.0` not `1`). Some endpoints may accept integers, but decimals are safer.

---

## 7. Field Name Casing Reference

The Evermore API has **inconsistent field name casing** across endpoints. This table documents the exact casing per endpoint:

| Field Concept | LoginRequest | OrderEntry | OrderStatus | ModifyRequest | CancelRequest | OrderBook | TradeBook | PositionRequest |
|---------------|-------------|------------|-------------|---------------|---------------|-----------|-----------|-----------------|
| Unique ID | — | `Uniqueid` | `Uniqueid` | `Uniqueid` | `UniqueId` | `UniqueId` | `UniqueId` | `Uniqueid` |
| Ref No | — | `RefNo` | `RefNo` | `RefNo` | `RefNo` | `RefNo` | `RefNo` | `RefNo` |
| Order No | — | — | `IntordNo` | `IntordNo` | `IntOrdNo` | `IntOrdNo` | `IntOrdNo` | — |
| Buy/Sell | — | `Buysell` | — | — | — | `BuySell` | `BuySell` | — |
| Trigger Price | — | `Triggerprice` | — | `TriggerPrice` | — | `TriggerPrice` | — | — |
| Token No | — | `Tokenno` | — | — | — | `TokenNo` | `TokenNo` | `TokenNo` |
| Validity | — | `validity` | — | `Validity` | — | — | — | — |
| Client Code | — | `clientcode` | — | — | — | — | — | `ClientCode` |
| Delivery Type | — | `DeliveryType` | — | — | — | — | — | — |

> ⚠️ **Key inconsistencies to watch:**
> - `Uniqueid` vs `UniqueId` (lowercase 'i' in OrderEntry/Modify/Status/Position; uppercase in Cancel/OrderBook/TradeBook)
> - `IntordNo` vs `IntOrdNo` (lowercase 'o' in Status/Modify; uppercase in Cancel/OrderBook)
> - `Triggerprice` vs `TriggerPrice` (OrderEntry vs ModifyRequest)
> - `Buysell` vs `BuySell` (OrderEntry vs OrderBook response)
> - `validity` vs `Validity` (OrderEntry vs ModifyRequest)
> - `clientcode` vs `ClientCode` (OrderEntry vs PositionRequest)

---

## 8. Live API Test Results (2026-03-18)

All 8 REST endpoints were tested live against `http://192.168.6.164:16006`. Full order lifecycle completed successfully.

### Test Execution Summary

| Step | Endpoint | HTTP | Response Summary | Status |
|------|----------|------|------------------|--------|
| 1 | LoginRequest | 200 | `UniqueId: 29, RefNo: "MxTmI8eE3kiVrsaqOjuATaRFdtxCPaU8", Error: null` | ✅ PASS |
| 2 | OrderBookRequest | 200 | `[]` (empty — no prior orders) | ✅ PASS |
| 3 | TradeBookRequest | 200 | `[]` (empty — no trades) | ✅ PASS |
| 4 | PositionRequest | 200 | `[]` (empty — no positions) | ✅ PASS |
| 5 | OrderEntry (BUY RELIANCE @ ₹1) | 200 | `IntOrdNo: 1, Error: null, BuySell: "BUY", Price: 1.00` | ✅ PASS |
| 6 | OrderStatusRequest | 200 | `"EPending"` | ✅ PASS |
| 7 | ModifyRequest (Price → ₹2) | 200 | `IntOrdNo: 1, Error: null` | ✅ PASS |
| 8 | CancelRequest | 200 | `IntOrdNo: 1, Error: null` | ✅ PASS |
| 9 | OrderBookRequest (verify) | 200 | `OrderStatus: "ECancelled", OrderPrice: 2.00, ExchOrdNo: "202403000159304"` | ✅ PASS |

### Key Observations from Live Testing

1. **OrderEntry response includes extra fields** not in docs: `BuySell`, `Price`, `Triggerprice` are echoed back alongside `IntOrdNo` and `Error`.

2. **ModifyRequest/CancelRequest responses** return `BuySell: null` and `Price: 0.0` — the actual modification is only confirmed via OrderBookRequest (which showed updated price of ₹2.00).

3. **OrderStatus returned `"EPending"`** — the docs list `"EPEnding"` (capital 'E' in "Ending"). Actual value has lowercase 'e': `EPending`. Similarly, cancelled status is `"ECancelled"` (not `"Ecancelled"` as in docs).

4. **Full lifecycle confirmed:** Place at ₹1.00 → Status EPending → Modify to ₹2.00 → Cancel → Final OrderBook shows `ECancelled` at price ₹2.00.

5. **Error field is `null`** (not empty string `""`) on success — the docs say "empty" but the actual API returns JSON `null`.

### Discrepancies: Documentation vs Actual API

| Aspect | Documentation Says | Actual Behavior |
|--------|-------------------|-----------------|
| Error field on success | Empty string `""` | JSON `null` |
| OrderStatus "EPEnding" | `EPEnding` (capital E) | `EPending` (lowercase e) |
| OrderStatus "Ecancelled" | `Ecancelled` (lowercase c) | `ECancelled` (capital C) |
| OrderEntry response | Only `IntOrdNo` + `Error` | Also includes `BuySell`, `Price`, `Triggerprice` |
| Modify/Cancel response | Only `IntOrdNo` + `Error` | Also includes `BuySell` (null), `Price` (0.0), `Triggerprice` (0.0) |

> ⚠️ **QA Recommendation:** When coding against this API, use case-insensitive string comparison for status values and check for both `null` and `""` when evaluating the Error field.

---

## 9. Live WebSocket Feed Test Results (2026-03-18)

All WebSocket message types were tested live against `ws://192.168.6.164:19101`.

> **Note:** The documented UAT endpoint `ws://115.242.15.134:19101` was unreachable. The working WebSocket endpoint is on the same host as the REST API: `ws://192.168.6.164:19101`.

### Test Execution Summary

| # | Test | Result | Details |
|---|------|--------|---------|
| 1 | WebSocket Connection | ✅ PASS | Connected to `ws://192.168.6.164:19101` |
| 2 | Login | ✅ PASS | LoginId=DAKS, Version=V1.0, Xchgs=NSECM,NSEFO,NSECD,BSE,BSEFO,BSECD |
| 3 | Post-login IndexData | ✅ PASS | 65 IndexData messages received, Index: NIFTYBANK |
| 4 | FeedStatus | ℹ️ INFO | Not received in 5s window (may be sent only on status change) |
| 5 | Info message | ℹ️ INFO | Not received in 5s window (expected — server sends on-demand) |
| 6 | MarketData subscribe (RELIANCE) | ✅ PASS | 25 msgs received, all 22 expected fields present |
| 7 | MarketData sample data | ℹ️ INFO | LTP=1408.8, O=1397.2, H=1412.9, L=1397.2, C=1397.6, TTQ=6,761,604 |
| 8 | MarketData field validation | ✅ PASS | All 22 fields present (Xchg, Tkn, LTP, LTQ, LUT, LTT, ATP, BQ, BP, SQ, SP, TBQ, TSQ, TTQ, TTV, OI, O, H, L, C, DPRL, DPRH) |
| 9 | Depth subscribe (RELIANCE) | ✅ PASS | 21 msgs with 5-level depth data |
| 10 | Greeks subscribe (NIFTY option) | ℹ️ INFO | No Greek messages in 8s (token 57133 may need a valid options contract token) |
| 11 | Unsubscribe MarketData | ✅ PASS | Before: 12 msgs → After: 0 msgs (confirmed unsubscribe works) |
| 12 | Heartbeat (Info HB) | ✅ PASS | Connection alive after heartbeat |
| 13 | OChain (NIFTY) | ℹ️ INFO | No OChain messages in 10s (expiry 19-03-2026 — verify expiry date format) |
| 14 | SnapQuote (TCS, FeedType=3) | ℹ️ INFO | No SnapQuote messages in 8s (may not be enabled on this server) |
| 15 | Multi-token subscription | ✅ PASS | 68 msgs for 3 tokens: RELIANCE (2885), TCS (11536), INFY (1594) |
| 16 | Cleanup unsubscribe | ✅ PASS | All subscriptions cleared, connection stable |
| 17 | Logout | ✅ PASS | Response: "Logout Successfully on Request" |

### Results: **11 PASS | 0 FAIL | 6 INFO**

### Key Observations from Live WebSocket Testing

1. **Working endpoint differs from docs:** The documented UAT `ws://115.242.15.134:19101` was unreachable. The actual working endpoint is `ws://192.168.6.164:19101` (same host as REST API).

2. **Login response confirmed:** Version=`V1.0`, Exchanges=`NSECM,NSEFO,NSECD,BSE,BSEFO,BSECD` (6 exchanges — docs mentioned 4).

3. **MarketData works perfectly:** All 22 documented fields are present. Real-time RELIANCE data: LTP ₹1,408.80.

4. **Depth works perfectly:** 5-level bid/ask depth received with all 6 fields per level (BO, BP, BQ, SQ, SP, SO).

5. **Unsubscribe confirmed working:** MarketData messages dropped from 12→0 after unsubscribe.

6. **Multi-token subscription works:** 3 tokens subscribed simultaneously, all received data.

7. **Greeks/OChain/SnapQuote need investigation:**
   - **Greeks (FeedType=4):** Token `57133` may be a futures token, not options. Try with a specific CE/PE token.
   - **OChain:** Expiry date format or the specific expiry may not match available contracts.
   - **SnapQuote (FeedType=3):** May not be enabled on this server or may return data differently.

8. **IndexData floods on login:** 65 IndexData messages received immediately after login — consider filtering/throttling in production.

9. **Logout response is clean:** `"Logout Successfully on Request"` — connection closes gracefully.

### Discrepancies: Documentation vs Actual (WebSocket)

| Aspect | Documentation Says | Actual Behavior |
|--------|-------------------|-----------------|
| UAT Endpoint | `ws://115.242.15.134:19101` | `ws://192.168.6.164:19101` (different host) |
| Exchanges | NSECM, NSEFO (2 mentioned in examples) | NSECM, NSEFO, NSECD, BSE, BSEFO, BSECD (6 total) |
| FeedStatus timing | Sent after login | Not observed in 5s post-login window |
| Logout response | `"Logged out successfully"` (example) | `"Logout Successfully on Request"` |

### Test Script

The full test script is saved at: `evermoredocs/ws_feed_test.js`

Run it with:
```bash
cd evermoredocs && node ws_feed_test.js
```

> To test against a different endpoint, edit the `WS_URL` constant at the top of the script.

---

*End of API Testing Guide*
