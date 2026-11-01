# `DISPLAY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata は `DISPLAY` を Linux のグラフィカルデスクトップセッションの有無を判定する目印として読みます。`WAYLAND_DISPLAY` と同列に扱い、判定は主に AMD HIP 環境向けの VRAM 予約量の推奨表示に使われます。`DISPLAY` の値を X server へ接続したり、GPU の動作を切り替えたりする処理は Strata 内には見つかりません。

デスクトップアプリの診断ログ収集も `DISPLAY` が設定されていれば値を記録します。これは描画用の設定をログに添える処理であり、ログ以外の実行動作を変えません。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 設定時の判定 |
|---|---|---|
| `setup.py:7508-7511` | `env.get(...)` は未設定で `None`、空文字列は偽。どちらも `DISPLAY` 単独ではデスクトップ判定にならない | 空でない任意の文字列を真として扱う。値の形式・数値・先頭文字は検査しない |
| `serve/server.py:8227-8230` | 同じく未設定・空文字列は偽 | 空でない任意の文字列を真として扱う。値は parse しない |
| `apps/desktop/src-tauri/src/desktoplog.rs:187-193` | 未設定なら出力対象外。空文字列は `DISPLAY=` として記録される | Unicode として取得できた値をそのまま `DISPLAY=<値>` として記録する |

setup と server の判定はいずれも `WAYLAND_DISPLAY` または `DISPLAY` のどちらかが真なら成立します。したがって、`WAYLAND_DISPLAY` が空または未設定で `DISPLAY` が空でなければ成立し、両方が空なら成立しません。値同士の優先順位や `DISPLAY` の既定値はありません。環境変数値は呼び出し時のプロセス環境から読み、Strata 側の static cache はありません。

## 有効になる条件

- **setup の推奨**: `setup.py:10282-10284` では、HIP backend で、`--vram-reserve-mib` が指定されておらず、`linux_desktop()` が真のときに AMD デスクトップ向けの案内を表示します。setup 側の判定は `sys.platform.startswith("linux")` も必要です（`setup.py:7508-7511`）。案内は `--vram-reserve-mib 3072` を提案するだけで、設定を自動変更しません（`setup.py:7514-7520`）。
- **サーバー起動後の note**: `serve/server.py:9282-9285` は単一 engine（replica groups でも layer split でもない）の起動後に判定し、条件を満たす場合は note を標準出力へ表示します。`desktop_vram_note()` は backend が `hip`、デスクトップ判定が真、engine 情報の `vram_free_mib` が整数かつ 2048 未満の場合にだけ対象になります（`serve/server.py:8233-8239`）。この helper の OS 条件は `os.name != "nt"` かつ `sys.platform != "darwin"` です（`serve/server.py:8227-8230`）。
- server note の既定 reserve は 700 MiB です。engine 引数 `--vram-reserve-mib N` が存在すれば整数変換した値を使い、3072 MiB 以上なら note を出しません。引数値が欠けているか整数変換できない場合は 700 MiB に戻ります（`serve/server.py:8240-8250`）。setup の CLI 値がある場合は setup のデスクトップ案内を抑止し、server 側でも engine 引数を基に note の要否を決めます（`setup.py:9185-9187,10230-10240`; `serve/server.py:8240-8245`）。
- **診断ログ**: OS/backend 条件による分岐はなく、デスクトップアプリが crash report または `--save-logs` の文章を組み立てるときに graphics environment 一覧へ含めます（`apps/desktop/src-tauri/src/desktoplog.rs:186-193,241-259,310-319`）。

## 実行時の詳細

setup の `linux_desktop(env=None)` は引数 `env` があればその辞書、なければ `os.environ` を参照します。確認できた本番呼び出しは `setup.py:10282` で、引数を渡さないため現在のプロセス環境を使います。判定を呼び出すたびに行い、結果をキャッシュしません。`DISPLAY` または `WAYLAND_DISPLAY` があっても、setup は HIP 以外、`--vram-reserve-mib` 指定済み、または上記の分岐に入らない場合にはこの案内を出しません。

server も `linux_desktop(env=None)` の引数が省略されると `os.environ` を参照し、`desktop_vram_note()` に真偽値を渡します。`DISPLAY` は engine の環境に転送するためにこのコードで読み取られているのではなく、ホスト側で起動後の案内を判定するために読まれます。note は `[strata] note: ...` で始まり、推奨 reserve と、現在の reserve との差に基づく expert cache の減少量を示します（`serve/server.py:8246-8250,9278-9285`）。推奨値は実行時に適用されません。

デスクトップアプリは crash report の `Graphics session:` 節と `--save-logs` の出力に、環境に存在する graphics variables を追加します。`DISPLAY` の値がログへ現れるのはこの診断経路です（`apps/desktop/src-tauri/src/desktoplog.rs:241-259,310-319`）。

## 根拠

- 環境値の desktop 判定と setup での実呼び出し: `setup.py:7508-7511,10282-10284`
- setup の推奨文と CLI reserve の適用: `setup.py:7514-7520,9185-9187,10230-10240`
- server の desktop 判定、条件、reserve fallback、note 文: `serve/server.py:8227-8250`
- 起動後の呼び出しと出力: `serve/server.py:9278-9285`
- デスクトップ診断ログへの値の収集と利用: `apps/desktop/src-tauri/src/desktoplog.rs:186-193,241-259,310-319`

`000_envvers.md` の他の一致箇所も確認しました。`DISPLAY_RESERVE_MIB` は setup 内の定数、Windows の `_DISPLAY_CLASS` はレジストリキー名、`ES_DISPLAY_REQUIRED` はコメント中の Windows API 定数名であり、これらは `DISPLAY` 環境変数の読み取りではありません。テストや同梱 KaTeX vendor 内の一致は本番実装の根拠にしていません。
