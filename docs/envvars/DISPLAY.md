# `DISPLAY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata のサーバーは `DISPLAY` を Linux のグラフィカルセッション有無を推定する材料の一つとして読みます。`WAYLAND_DISPLAY` が空または未設定で `DISPLAY` が非空ならデスクトップありと判定し、単一エンジンの起動後に HIP backend の VRAM 空き容量が少ない場合、VRAM 予約量を増やす案内を出します。この変数自体が予約量や GPU 動作を変更するわけではありません（`terminal/serve/server_parts/http_api.py:119-142`、`terminal/serve/server.py:8961-8967`）。

デスクトップアプリでは、クラッシュ診断と `--save-logs` がグラフィックス環境の一覧に `DISPLAY` を含め、環境に設定されている値を診断出力へ記録します。ここでは設定による分岐やウィンドウ動作の変更はありません（`app/desktop/src-tauri/src/desktoplog.rs:186-193,245-259,310-320`）。

## 値と判定

| 読み取り箇所 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| サーバーのデスクトップ判定 | `WAYLAND_DISPLAY` も未設定または空なら false | Linux 上で `WAYLAND_DISPLAY` が空のとき `:0` など非空の値 | 未設定、空文字。`WAYLAND_DISPLAY` が非空なら `DISPLAY` は参照結果に影響しない |
| デスクトップ診断 | 一覧に出ない | 設定された文字列をそのまま `DISPLAY=<値>` として出力 | 空文字も `std::env::var` では取得できるため空の値として記録される。未設定または Unicode 文字列に変換できない値は出ない |

サーバー判定は値の内容を parse せず、Python の `env.get("WAYLAND_DISPLAY") or env.get("DISPLAY")` の真偽値を使います。空白だけの文字列も非空なので true です。値の形式、大文字小文字、数値としての妥当性は検査しません。未設定と空文字はいずれもこの判定では false です（`terminal/serve/server_parts/http_api.py:119-122`）。診断側は `std::env::var` が `Ok` を返したとき値を記録し、値の内容は判定しません（`app/desktop/src-tauri/src/desktoplog.rs:187-193`）。

## 有効になる条件

- サーバー側の判定は `os.name != "nt"` かつ `sys.platform != "darwin"` のときだけ行われます。Strata の関数はこれを Linux のデスクトップ判定に使います（`terminal/serve/server_parts/http_api.py:119-122`）。
- デスクトップ判定が案内につながるのは、実サーバーの通常の単一エンジン経路（GPU groups なし、split 起動なし）で、設定 backend が `hip`、モデル読み込み後の `vram_free_mib` が整数かつ 2048 MiB 未満の場合です（`terminal/serve/server.py:8956-8967`、`terminal/serve/server_parts/http_api.py:113-130`）。
- さらに `--vram-reserve-mib` が未指定なら 700 MiB として案内量を計算します。指定値を `int` 変換できない、または引数が欠けている場合も 700 MiB に戻ります。予約量が 3072 MiB 以上なら案内しません（`terminal/serve/server_parts/http_api.py:125-142`）。
- `WAYLAND_DISPLAY` が非空なら、それだけでデスクトップ判定は true になり、`DISPLAY` の値は判定に関与しません（`terminal/serve/server_parts/http_api.py:121-122`）。
- `terminal/setup.py` にも Linux 判定関数と `DISPLAY_RESERVE_MIB` 定数がありますが、この関数の呼び出し箇所は現行ソースに見つからず、`DISPLAY` による setup 時の動作は確認できません（`terminal/setup.py:8933-8949`）。

## 実行時の詳細

サーバーでは `linux_desktop()` の呼び出しごとに `os.environ` を参照し、値をキャッシュしません。サーバー起動後にプロセス環境が変われば次回呼び出し時の判定に反映されますが、この判定は起動後のエンジン初期化直後に案内を作る箇所で呼ばれます（`terminal/serve/server_parts/http_api.py:119-122`、`terminal/serve/server.py:8961-8967`）。

条件を満たす場合、Strata は標準出力へ `print(note, flush=True)` で `[strata] note: ...` の案内を出します。これは `--vram-reserve-mib 3072` を勧めるメッセージであり、現在の起動設定を変更したり、モデルを終了したりする処理ではありません。backend が HIP 以外、デスクトップ判定が false、VRAM 空き情報が未取得または 2048 MiB 以上、groups/split 起動、あるいは予約量が 3072 MiB 以上なら、この案内は出ません（`terminal/serve/server_parts/http_api.py:125-142`、`terminal/serve/server.py:8964-8967`）。

デスクトップアプリのクラッシュログでは環境一覧を作成する時点で値を読み、`Graphics session:` の下に記録します。`--save-logs` でも同じ一覧を含む診断ファイルを生成します。これらの箇所に `DISPLAY` を設定・削除して子プロセスへ渡す処理はありません（`app/desktop/src-tauri/src/desktoplog.rs:186-193,245-259,310-320`）。

## ログと測定値

サーバーの案内文字列は次の形式です（条件を満たさない場合は出力しません）。

```text
[strata] note: <空きMiB> MiB of VRAM free with the model loaded. If this AMD card also drives your desktop and the desktop or apps crash after the start (the driver moves the expert cache to RAM and the OOM killer ends the session), keep more VRAM free: ./setup.sh --vram-reserve-mib 3072 (remembered; the expert cache gets <計算値> GB less, a few % of speed)
```

診断ログでは設定されている場合に `DISPLAY=<値>` がグラフィックス環境情報として含まれます。これは値の記録であり、Strata が表示先や描画方式を設定するログではありません（`app/desktop/src-tauri/src/desktoplog.rs:187-193,254-259,319`）。

## 根拠

- `terminal/serve/server_parts/http_api.py:113-142` — デスクトップ判定と、HIP / VRAM / `--vram-reserve-mib` 条件による案内文。
- `terminal/serve/server.py:8956-8967` — 起動経路と案内の呼び出し・出力。
- `terminal/setup.py:8933-8949` — setup 内の未使用判定関数と案内関数。
- `app/desktop/src-tauri/src/desktoplog.rs:186-193,245-259,310-320` — グラフィックス環境変数の読み取りと診断出力。
