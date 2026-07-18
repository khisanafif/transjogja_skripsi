const BASE = import.meta.env.VITE_API_URL || '/api'

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  getStops:         ()          => req('GET', '/stops'),
  getNearestStops:  (lat, lon)  => req('GET', `/stops/nearest?lat=${lat}&lon=${lon}`),
  getStop:          (id)        => req('GET', `/stops/${id}`),
  getPoi:           (type)      => req('GET', type ? `/poi?type=${type}` : '/poi'),
  getPoiTypes:      ()          => req('GET', '/poi/types'),
  getPoiDetail:     (id)        => req('GET', `/poi/${id}`),
  recommend:        (body)      => req('POST', '/recommend', body),
  routeTo:          (body)      => req('POST', '/route', body),
  itinerary:        (body)      => req('POST', '/itinerary', body),
  getSchedule:      (stop_id, day_type) => req('GET', `/schedule?stop_id=${stop_id}&day_type=${day_type||'weekday'}`).then(data => ({
    stop_name: data.stop_name,
    routes: data.routes
  })),
  getRoutesList:    ()          => req('GET', '/routes'),
  getRouteDetail:   (rd)        => req('GET', `/routes/${rd}`),
  getRoutesGeoJSON: (id)        => req('GET', id ? `/routes/geojson?route_id=${id}` : '/routes/geojson'),
  getRoutesBetween: (from, to)  => req('GET', `/routes/between/stops?from_stop=${from}&to_stop=${to}`),
}
