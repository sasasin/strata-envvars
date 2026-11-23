# `STRATA_DESKTOP_TEST_PANIC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows/macOS の Strata Desktop で、Tauri の setup 中に意図的な panic を起こす診断用フック。setup エラー時に panic hook が失敗を記録する仕組みを、正常に起動する環境で確認する用途として置かれている。アプリ本体やエンジンの計算設定を変えるものではない。チェックは `run_embedded()` の Tauri `.setup()` callback 内にあるため、通常の Windows/macOS デスクトップ起動経路でのみ評価される（`app/desktop/src-tauri/src/main.rs:947-949,977-981`）。

## 値と判定

`std::env::var_os(...).is_some()` により、値の文字列や Unicode 変換をせず、変数が存在するかだけを見る。未設定なら何もしない。空文字を含む設定済みの値はすべて同じ扱いで panic し、`1`、`0`、`false`、任意文字列でも区別されない（`app/desktop/src-tauri/src/main.rs:979-980`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Windows/macOS の通常の Desktop 起動で `.setup()` に到達 | panic しない | 空文字を含む、存在するすべての値 | なし（値内容を検査しない） |
| Linux Desktop | この名前の読み取りコードがなく、効果なし | 該当なし | 該当なし |
| `--self-test[=path]` を指定した起動 | self-test に進む | このチェックには到達しない | 該当なし |

## 有効になる条件

- ビルド対象が Linux 以外であること。`run_embedded()` とその setup callback は `#[cfg(not(target_os = "linux"))]` 側にあり、Linux は supervisor/window-process 経路へ進む（`app/desktop/src-tauri/src/main.rs:929-944,947-949`）。
- `--self-test[=path]` でないこと。self-test は `run_embedded()` より前に処理され、結果コードで終了する（`app/desktop/src-tauri/src/main.rs:924-926,943-944`）。
- Tauri setup callback まで起動が進むこと。変数が設定されていると callback 内で panic するため、`start_host()` と `open_window()` は呼ばれない（`app/desktop/src-tauri/src/main.rs:977-995`）。
- debug/release の値判定に分岐はない。release profile は `panic = "abort"`（`app/desktop/src-tauri/Cargo.toml:37-42`）。
- `STRATA_NO_DIALOG` が存在する場合（空文字を含む）は `desktoplog` の起動時設定でダイアログが無効になる。panic 自体は抑止されず、失敗記録の経路は実行される（`app/desktop/src-tauri/src/desktoplog.rs:363-370,484-488`）。

## 実行時の詳細

main は Windows/macOS で `run_embedded()` に入る前に `desktoplog::init_startup(...)` を呼び、run log と panic hook を初期化する。`--self-test` の場合はその前に別経路へ進む（`app/desktop/src-tauri/src/main.rs:909-926,943-949`; `app/desktop/src-tauri/src/desktoplog.rs:363-371`）。環境変数は `.setup()` callback が走った時点でその都度読み取られ、値を保持する cache はない。設定済みなら文字列 `STRATA_DESKTOP_TEST_PANIC is set: the app panics on purpose` で panic し、callback 内の後続の host 起動・window 作成には進まない（`app/desktop/src-tauri/src/main.rs:977-995`）。

panic hook は元の hook を呼んでから panic payload と場所・thread 名を取り出し、`report_failure` に渡す。run log に `START FAILED: the app stopped unexpectedly: ...` を記録し、起動失敗ファイルを書き、保存先をログにも記録する。ダイアログが有効なら `Strata could not start.` で始まるエラー表示を行う（`app/desktop/src-tauri/src/desktoplog.rs:472-488,497-513`）。release build は `panic = "abort"` であり、hook の処理後に abort する（`app/desktop/src-tauri/Cargo.toml:37-42`）。debug build の panic 後の最終的な終了方法は、この環境変数の読み取り箇所だけからは特定しない。

## ログと測定値

測定値は該当しない。panic hook が run log に書く失敗行の形式は `START FAILED: the app stopped unexpectedly: {message} (at {file}:{line}, thread {thread})`。設定値による通常ログや値の表示はなく、panic 時には crash file の保存先を `The crash file is {path}` と記録する（`app/desktop/src-tauri/src/desktoplog.rs:478-488,503-513`）。Strata の `docs/DETAILS.md` を含む文書群には、この変数の追加動作を説明する該当記述は見つからなかった。

## 根拠

- `app/desktop/src-tauri/src/main.rs:901-945` — main の起動順、self-test と Linux の分岐。
- `app/desktop/src-tauri/src/main.rs:947-995` — 非 Linux の埋め込み起動、設定有無判定、panic の位置とその後に続く処理。
- `app/desktop/src-tauri/src/desktoplog.rs:363-371,472-513` — 起動ログ・panic hook・失敗記録・ダイアログ。
- `app/desktop/src-tauri/Cargo.toml:37-42` — release の panic 設定。
