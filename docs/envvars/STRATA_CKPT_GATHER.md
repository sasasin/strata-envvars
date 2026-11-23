# `STRATA_CKPT_GATHER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の会話チェックポイント保存で、小さな実行状態ベクトルを一時バッファへ集約し、ホストへまとめてコピーする経路を選びます。対象は `ple`、各所有 QSA レイヤーの indexer tail・dead row・block position です。未設定時などはそれぞれを個別にコピーします。保存データの内容はどちらの経路でも同じです。`conversation_checkpoint_save` は生成中のチェックポイントと会話スナップショット保存から呼ばれます（`engine/src/core/conversation_state.cpp:222-227,391-407,411-415,563-568,703-714`、`engine/src/program/generate.cpp:2561-2566,14587-14608`）。

## 値と判定

関数内 static 初期化で `std::getenv` の値を読み、ポインターが非 null で、先頭バイトが文字 `'1'` の場合だけ有効にします。文字列全体の比較や数値変換はしません（`engine/src/core/conversation_state.cpp:230-236`）。

| ビルド条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` のいずれも定義されない場合 | 無効 | `1`、`10`、`1anything` など先頭が `1` | 空文字、`0`、`true`、` 1`、`-1` など先頭が `1` 以外 |
| 上記いずれかが定義される場合 | 無効 | なし（値を読み取らず常に無効） | すべて |

空白の trim、大文字小文字の変換、数字としての妥当性検査はありません。`ckpt_gather_on()` の最初の呼び出し時に一度だけ値を読み、結果を関数内 `static` に保持します。その後の環境変更は同プロセスでは反映されません（`engine/src/core/conversation_state.cpp:230-236`）。

## 有効になる条件

- HIP、HIP gfx906、Metal のビルドでは無効です。これらの macro がない CUDA 実装経路で有効になり得ます（`engine/src/core/conversation_state.cpp:230-236`）。
- 会話チェックポイントの保存処理が実行される必要があります。復元処理ではこのスイッチを参照しません（`engine/src/core/conversation_state.cpp:391-407,417-455`）。
- `STRATA_CKPT_ASYNC` は必須ではありません。これは別の大きな GDN 状態のコピー経路を制御し、小ベクトルの gather 分岐はその後に独立して評価されます（`engine/src/core/conversation_state.cpp:319-388,390-404`）。
- 層分割時は各 stage の所有状態を保存します。gather 用の一組のバッファは mutex で保護され、同じバッファを使う保存呼び出しを直列化します（`engine/src/core/conversation_state.cpp:222-229,239-255`）。
- gather 用のデバイスバッファまたは pinned host バッファを確保できない場合、gather は無効扱いとなり、個別コピーへ fallback します（`engine/src/core/conversation_state.cpp:244-258,392-403`）。

## 実行時の詳細

保存ごとに、存在する `ple` と所有レイヤーの tail・dead row・block position のサイズを合計します。合計が 0 ならコピーなしで成功します。必要なバッファは初回に確保し、その後は容量と device が合う限り再利用します。必要容量が増えた場合や device が変わった場合は既存バッファを解放して確保し直します（`engine/src/core/conversation_state.cpp:239-258`）。

有効時は各状態を同じ device バッファへ順に device-to-device コピーし、そのバッファを一度 host へコピーして、元のチェックポイント配列へ `memcpy` します。無効時、または確保失敗時は各配列を個別にコピーします（`engine/src/core/conversation_state.cpp:259-274,390-404`）。コピー失敗時はこの fallback に切り替えず保存失敗になります。通常の保存ラッパーは `strata serve: checkpoint save: <理由>` を stderr に出します（`engine/src/core/conversation_state.cpp:41-47,259-274,392-407`、`engine/src/program/generate.cpp:2561-2566`）。

読み取りは engine プロセス内の `ckpt_gather_on()` に限られ、候補名の全参照にも子プロセスへの転送処理はありません。CLI 引数や別の環境変数による値の上書きも、このスイッチの判定にはありません（`engine/src/core/conversation_state.cpp:230-236,391-404`）。

## ログと測定値

このスイッチ専用の有効・無効ログはありません。gather バッファの確保失敗もログを出さず個別コピーへ進みます。コピー失敗は `strata serve: checkpoint save: <理由>` として出力され、層分割の一部チェックポイントでは、GPU が継続可能な場合に `strata serve: checkpoint at %lld skipped: stage %zu's state could not be copied out (see above); the request goes on without it` が出ます（`engine/src/core/conversation_state.cpp:253-258,391-404`、`engine/src/program/generate.cpp:2561-2566,14776-14784`）。

`docs/DETAILS.md:1774` は小コピーを 37 個から 1 回にまとめると記し、層分割での測定はしていないとしています。これは資料上の記述であり、独立した速度測定値は示されていません。現在の実装には層分割時に共有バッファを mutex で保護する処理があります（`engine/src/core/conversation_state.cpp:222-229,244-274`）。

## 根拠

- `engine/src/core/conversation_state.cpp:222-236` — スイッチの対象、backend macro 条件、値判定、static cache。
- `engine/src/core/conversation_state.cpp:239-274,390-407` — バッファの確保・再利用、gather と個別コピーの経路、失敗時の扱い。
- `engine/src/core/conversation_state.cpp:411-415,563-568,703-714`、`engine/src/program/generate.cpp:14587-14608` — 保存処理の呼び出し元。
- `engine/src/program/generate.cpp:2561-2566,14776-14784` — 保存失敗時のログと一部チェックポイントの扱い。
- `docs/DETAILS.md:1762-1775` — 資料上の適用範囲と測定記述。
