// netlify/functions/odds-history.js
// Fetches historical pregame NBA spreads from The Odds API
// API key stored in Netlify env var ODDS_API_KEY — never exposed to browser

const ODDS_API_KEY  = process.env.ODDS_API_KEY;
const ODDS_BASE_URL = 'https://api.the-odds-api.com/v4';
const SPORT        = 'basketball_nba';

// P0-7: Same origin allowlist pattern as kalshi-order.js
const ALLOWED_ORIGINS = (process.env.KALSHI_ALLOWED_ORIGIN || '').split(',').map(s => s.trim()).filter(Boolean);

exports.handler = async (event) => {
  const origin = event.headers.origin || event.headers.Origin || '';
  const originOk = ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin);
  const cors = {
    'Access-Control-Allow-Origin': originOk ? (origin || '*') : 'null',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Vary': 'Origin',
  };

  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: cors, body: '' };
  if (!originOk)  return { statusCode: 403, headers: cors, body: JSON.stringify({ error: 'Forbidden' }) };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers: cors, body: JSON.stringify({ error: 'Method not allowed' }) };

  if (!ODDS_API_KEY) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: 'ODDS_API_KEY env var not set in Netlify' }) };
  }

  let body;
  try { body = JSON.parse(event.body || '{}'); }
  catch { return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Invalid JSON' }) }; }

  // action: 'historical_spreads'
  // date:   YYYYMMDD string (e.g. '20240225')
  const { action, date } = body;

  if (action !== 'historical_spreads') {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: `Unknown action: ${action}` }) };
  }

  if (!date || !/^\d{8}$/.test(date)) {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'date must be YYYYMMDD string' }) };
  }

  // Format date for Odds API: query at T22:00:00Z (≈6pm ET) — pre-game closing line
  // NBA games tip off between 19:00–02:00 ET (midnight–08:00 UTC), so 22:00 UTC is
  // before most tip-offs while markets are fully liquid.
  const iso = `${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}T22:00:00Z`;

  const url = new URL(`${ODDS_BASE_URL}/sports/${SPORT}/odds-history/`);
  url.searchParams.set('apiKey',      ODDS_API_KEY);
  url.searchParams.set('regions',     'us');
  url.searchParams.set('markets',     'spreads');
  url.searchParams.set('oddsFormat',  'american');
  url.searchParams.set('date',        iso);

  let oddsResp;
  try {
    oddsResp = await fetch(url.toString());
  } catch (e) {
    return { statusCode: 502, headers: cors, body: JSON.stringify({ error: `Odds API fetch failed: ${e.message}` }) };
  }

  const remaining = oddsResp.headers.get('x-requests-remaining') ?? 'unknown';
  const used      = oddsResp.headers.get('x-requests-used')      ?? 'unknown';

  if (!oddsResp.ok) {
    const txt = await oddsResp.text();
    return { statusCode: oddsResp.status, headers: cors, body: JSON.stringify({ error: `Odds API error ${oddsResp.status}`, detail: txt }) };
  }

  const games = await oddsResp.json();

  // ── Process into a lean lookup map ─────────────────────────────────────────
  // Key:   "HOME_ABBR|AWAY_ABBR"  (ESPN abbreviations — see ODDS_TEAM_NAME_TO_ESPN below)
  // Value: { spreadHome: float, book: string }
  //        spreadHome is the home team's spread point (negative = favored)
  //
  // We store both orientations so callers can look up either home or away team.

  const ODDS_TEAM_NAME_TO_ESPN = {
    'Atlanta Hawks':          'ATL',
    'Boston Celtics':         'BOS',
    'Brooklyn Nets':          'BKN',
    'Charlotte Hornets':      'CHA',
    'Chicago Bulls':          'CHI',
    'Cleveland Cavaliers':    'CLE',
    'Dallas Mavericks':       'DAL',
    'Denver Nuggets':         'DEN',
    'Detroit Pistons':        'DET',
    'Golden State Warriors':  'GS',
    'Houston Rockets':        'HOU',
    'Indiana Pacers':         'IND',
    'Los Angeles Clippers':   'LAC',
    'Los Angeles Lakers':     'LAL',
    'Memphis Grizzlies':      'MEM',
    'Miami Heat':             'MIA',
    'Milwaukee Bucks':        'MIL',
    'Minnesota Timberwolves': 'MIN',
    'New Orleans Pelicans':   'NO',
    'New York Knicks':        'NY',
    'Oklahoma City Thunder':  'OKC',
    'Orlando Magic':          'ORL',
    'Philadelphia 76ers':     'PHI',
    'Phoenix Suns':           'PHX',
    'Portland Trail Blazers': 'POR',
    'Sacramento Kings':       'SAC',
    'San Antonio Spurs':      'SA',
    'Toronto Raptors':        'TOR',
    'Utah Jazz':              'UTAH',
    'Washington Wizards':     'WSH',
  };

  const spreadMap = {}; // "HOME|AWAY" → { spreadHome, book }

  for (const game of (Array.isArray(games) ? games : [])) {
    const homeAbbr = ODDS_TEAM_NAME_TO_ESPN[game.home_team];
    const awayAbbr = ODDS_TEAM_NAME_TO_ESPN[game.away_team];
    if (!homeAbbr || !awayAbbr) continue;

    // Find the best (DraftKings preferred, then first available) spread line
    let spreadHome = null, book = null;
    const bookmakers = game.bookmakers || [];

    // Priority: DraftKings → FanDuel → any
    const priority = ['draftkings', 'fanduel'];
    let chosenBook = bookmakers.find(b => priority[0] === b.key)
                  || bookmakers.find(b => priority[1] === b.key)
                  || bookmakers[0];

    if (chosenBook) {
      const spreadMarket = (chosenBook.markets || []).find(m => m.key === 'spreads');
      if (spreadMarket) {
        const homeOutcome = (spreadMarket.outcomes || []).find(o => o.name === game.home_team);
        if (homeOutcome && homeOutcome.point != null) {
          spreadHome = homeOutcome.point; // negative = home favored
          book = chosenBook.key;
        }
      }
    }

    if (spreadHome !== null) {
      spreadMap[`${homeAbbr}|${awayAbbr}`] = { spreadHome, book };
    }
  }

  return {
    statusCode: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      date,
      iso,
      gamesFound:   games.length,
      gamesMatched: Object.keys(spreadMap).length,
      spreadMap,
      usage: { remaining, used },
    }),
  };
};
