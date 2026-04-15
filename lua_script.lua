-- KEYS[1]  rate-limit key (hashed identifier)
-- ARGV[1]  window duration in milliseconds
-- ARGV[2]  request limit (N)
-- ARGV[3]  window duration in seconds (for EXPIRE)

local key       = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit     = tonumber(ARGV[2])
local window_s  = tonumber(ARGV[3])

local time = redis.call('TIME')
local now  = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local from = now - window_ms

redis.call('ZREMRANGEBYSCORE', key, 0, from)
redis.call('ZADD', key, now, now)
local count = redis.call('ZCARD', key)
redis.call('EXPIRE', key, window_s)

return { count, limit }