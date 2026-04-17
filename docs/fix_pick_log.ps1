# Migrates pick_log from Documents/JonnyParlay to Downloads/JonnyParlay
# Keeps only the 5 premium card picks for April 14, adds card_slot column

$src = "C:\Users\jono4\Documents\JonnyParlay\pick_log.csv"
$dst = "C:\Users\jono4\Documents\JonnyParlay\pick_log.csv"
$mlbSrc = "C:\Users\jono4\Documents\JonnyParlay\pick_log_mlb.csv"
$mlbDst = "C:\Users\jono4\Documents\JonnyParlay\pick_log_mlb.csv"

$newHeader = "date,run_time,run_type,sport,player,team,stat,line,direction,proj,win_prob,edge,odds,book,tier,pick_score,size,game,mode,result,closing_odds,card_slot"

# April 14 card picks -> slot number
$cardSlots = @{
    "beckettSennecke_SOG_2.5_under" = 1
    "samMalinski_SOG_2.5_under"     = 2
    "deniAvdija_3PM_1.5_over"       = 3
    "pelleLarsson_PTS_9.5_under"    = 4
    "lameloBall_REB_5.5_under"      = 5
}

$rows = Import-Csv $src
$output = @($newHeader)

foreach ($row in $rows) {
    if ($row.date -eq "2026-04-14") {
        $player = ($row.player.Trim().ToLower() -replace '\s+', '')
        $key    = "${player}_$($row.stat.Trim())_$($row.line.Trim())_$($row.direction.Trim().ToLower())"
        $slot   = $cardSlots[$key]
        if ($null -eq $slot) { continue }  # skip non-card picks
        $output += "$($row.date),$($row.run_time),$($row.run_type),$($row.sport),$($row.player),$($row.team),$($row.stat),$($row.line),$($row.direction),$($row.proj),$($row.win_prob),$($row.edge),$($row.odds),$($row.book),$($row.tier),$($row.pick_score),$($row.size),$($row.game),$($row.mode),$($row.result),$($row.closing_odds),$slot"
    } else {
        $output += "$($row.date),$($row.run_time),$($row.run_type),$($row.sport),$($row.player),$($row.team),$($row.stat),$($row.line),$($row.direction),$($row.proj),$($row.win_prob),$($row.edge),$($row.odds),$($row.book),$($row.tier),$($row.pick_score),$($row.size),$($row.game),$($row.mode),$($row.result),$($row.closing_odds),"
    }
}

$output | Set-Content $dst -Encoding UTF8
Write-Host "Done - $($output.Count - 1) rows written to pick_log.csv"
