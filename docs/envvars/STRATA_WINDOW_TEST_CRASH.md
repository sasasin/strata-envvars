# `STRATA_WINDOW_TEST_CRASH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Linux デスクトップのウィンドウ用子プロセスを、WebKit/Tauri の起動前に意図的に abort させるテスト用フックである。`run_window_process` がこの変数の設定有無を検出すると診断行を stderr に出し、`std::process::abort()` を呼ぶ。コメントは「ウィンドウが動作する環境で WebKit のクラッシュ時の安全網を確かめる」用途としている。通常の起動制御や推論設定ではない（`app/desktop/src-tauri/src/main.rs:1295-1306`）。

Linux では shell が App Host を起動して維持し、別プロセスの window child が画面を担当する。window child の異常終了を受けると shell は App Host を維持して browser mode に移行する（`app/desktop/src-tauri/src/supervisor.rs:1-14, 465-476, 581-594`）。

## 値と判定

文字列の内容や Unicode 変換を調べず、`std::env::var_os(...).is_some()` で環境変数が存在するかだけを判定する（`app/desktop/src-tauri/src/main.rs:1303`）。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Linux の window child | 分岐しない | 値が何であっても設定されていれば発火。空文字、`0`、`false`、任意の文字列を含む | 該当なし。値の内容による無効値判定はない |
| Linux 以外、または window child 以外 | この読み取り箇所を通らない | 該当なし | 該当なし |

したがって、`1` を要求する判定ではなく、`0` や空文字も設定されていれば有効である。数値変換、trim、大文字小文字比較、境界値処理、無効値時の fallback はない（`app/desktop/src-tauri/src/main.rs:1298-1306`）。

## 有効になる条件

- Linux 向けデスクトップ実行ファイルであること。この読み取り関数は `#[cfg(target_os = "linux")]` で Linux に限定される（`app/desktop/src-tauri/src/main.rs:1298-1299`）。
- 通常起動時に `--browser` を指定せず、`STRATA_UI=browser` による browser 起動も選ばれず、shell が window child を起動すること。browser 起動では shell はウィンドウを作らない（`app/desktop/src-tauri/src/supervisor.rs:43-53, 547-556`）。
- 子プロセスが shell によって起動された window child であること。Linux の `main` は `--window-child` と親 shell の確認を通った場合に `run_window_process` を呼ぶ（`app/desktop/src-tauri/src/main.rs:929-942`）。
- shell の子起動は親環境を継承し、`STRATA_WINDOW_PORT` などを上書きしているが、この変数を削除・上書きしていない。そのため起動環境に設定されていれば window child にも渡る（`app/desktop/src-tauri/src/supervisor.rs:390-400, 552-556`）。
- CLI 引数による値の上書きや、他の環境変数との優先順位はない。`--browser` / `STRATA_UI=browser` はウィンドウを作らず、このフックを実行しない経路を選ぶ。

## 実行時の詳細

`run_window_process` は `STRATA_WINDOW_PORT` と `STRATA_SHUTDOWN_TOKEN` を読んだ後、この変数を一度確認する。設定ありなら `eprintln!` で診断を出して直ちに abort するため、続くフォント設定、親プロセス監視スレッド、Tauri builder、WebKit ウィンドウ生成には進まない（`app/desktop/src-tauri/src/main.rs:1299-1325`）。この読み取りを static cache するコードはなく、window child の起動ごとに関数内で判定する。プロセス起動後の環境変更を監視する処理はない。

初回起動では shell が子の終了状態を監視する。子が成功終了でなく異常終了した場合、shell は `window_failed` を呼び、終了理由を記録してクラッシュログを書き、browser mode へ切り替え、セッションの mode を `browser` に更新する。App Host とエンジンはこの経路では停止しない（`app/desktop/src-tauri/src/supervisor.rs:465-476, 566-594`）。Unix の終了理由表示は abort シグナルを `signal 6 (abort)` と表す（`app/desktop/src-tauri/src/supervisor.rs:205-219`）。

## ログと測定値

設定ありの window child は stderr に次の文字列を出す（`app/desktop/src-tauri/src/main.rs:1303-1305`）。

```text
[strata] STRATA_WINDOW_TEST_CRASH is set: the window process aborts on purpose.
```

親 shell は標準出力・標準エラーを端末とログへ転送する。異常終了時は終了理由（abort なら `signal 6 (abort)`）を含む `The app window crashed (...)` を記録し、クラッシュログを作成して、`Strata opened in your browser because the app window couldn't start on this computer.` と通知する（`app/desktop/src-tauri/src/supervisor.rs:27, 452-462, 465-476, 205-219`）。計測値は該当しない。

## 根拠

- `app/desktop/src-tauri/src/main.rs:901-945` — self-test の後の Linux shell/window-child 分岐と呼び出し条件。
- `app/desktop/src-tauri/src/main.rs:1295-1325` — Linux 専用関数、環境変数判定、stderr、abort、および後続処理。
- `app/desktop/src-tauri/src/supervisor.rs:390-400, 452-476, 547-594` — window child の起動・出力転送・異常終了後の browser mode 移行。
- `app/desktop/src-tauri/src/supervisor.rs:205-219` — Unix シグナルの表示。
