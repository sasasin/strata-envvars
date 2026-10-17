# `STRATA_SLOT_COPY_DIRECT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

バッチ実行の会話状態をメイン session と batch slot の間で移すとき、一時的なホスト側 snapshot を作って restore する経路の代わりに、状態バッファ間を直接コピーします。対象は通常の running state（GDN state、PLe 履歴、QSA indexer の状態）と QSA の K/V です。slot への admission と、checkpoint を指定しない slot の resume で使われます。

## 値と判定

`src/program/generate.cpp` の関数内 static 変数として一度だけ読みます。`getenv()` の結果を文字列 parse せず、設定値の先頭文字だけを判定します。

| 値 | 結果 |
|---|---|
| 未設定 | 無効（従来の snapshot 経由） |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外 | 有効（例: `1`, `true`, `false`, `2`, ` 1`） |

大文字小文字や数値としての妥当性は検査しません。環境をプロセス実行中に変更しても、static 初期化後は反映されません。根拠: `src/program/generate.cpp:10741-10749`。

## 有効になる条件

この判定は `generate.cpp` の `--batch` slot 処理で参照されます。バッチ slot を使わない実行ではコピー経路に影響しません。コードには CUDA runtime の同期とコピーが使われています。各 stage の main session と対応する slot session は同じ device に配置され、同じ形に確保されていることを前提にします。異なる buffer layout などが検出されると直接コピー関数は失敗します (`src/program/generate.cpp:10750-10778`, `src/core/conversation_state.cpp:218-246`, `src/core/conversation_snapshot.cpp:223-251`)。

## 実行時の詳細

- slot へ状態を入れる `copy_to_slot()` は、環境変数が有効なら `direct_slot_copy(true, ...)` を呼びます。これは slot admission と、batch 中に一時停止した prompt の状態を slot に保存する処理の両方から呼ばれます (`src/program/generate.cpp:10781-10805,12822-12842,14630-14646`)。
- slot から状態を戻す `copy_from_slot()` は、checkpoint 指定がないときだけ `direct_slot_copy(false, ...)` を使います。checkpoint 指定がある resume は従来の checkpoint restore と K/V の save/restore を使います (`src/program/generate.cpp:10822-10854,12105-12118`)。
- 直接経路は各 device をコピー前に同期し、session state と各 QSA K/V buffer をコピーしてから再度同期します。コピー対象の K/V は状態の pool 設定によって device buffer または authoritative な host pool です。`STRATA_SLOT_COPY_BATCHSYNC` が有効なら、コピーを private stream に enqueue し、各 device で最後に同期する経路をコピー helper に指定します (`src/program/generate.cpp:10750-10779`; `src/core/conversation_state.cpp:218-246`; `src/core/conversation_snapshot.cpp:223-251`)。
- direct copy が失敗した場合、slot resume は stderr に `strata batch: restoring slot %d failed (%s); reading the prompt` を出し、prompt を先頭から読み直します。admission 時の失敗は `strata serve: batch admission failed: ...` として stderr に出し、その slot の継続をやめます (`src/program/generate.cpp:12105-12117,14630-14638`)。

## 根拠

- `src/program/generate.cpp:10741-10749` — 値の読み取りと既定値。
- `src/program/generate.cpp:10750-10854` — direct と従来経路、slot へのコピー／slot からの復元。
- `src/core/conversation_state.cpp:218-246` — running state の直接コピー内容。
- `src/core/conversation_snapshot.cpp:223-251` — QSA K/V buffer の直接コピーと residency 更新。
- `docs/BATCHING.md:110-118` — バッチ用 opt-in switch と説明。資料の表は `=1` の例を示すが、実装は `0` 始まり以外の先頭文字を有効として扱う。
