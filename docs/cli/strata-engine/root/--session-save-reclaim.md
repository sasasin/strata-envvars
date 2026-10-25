# `--session-save-reclaim`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--session-save-reclaim` |
| 別名 | なし |
| 値 | なし（真偽フラグ） |

## 役割

`--serve` の対話プロトコルで `SAVE <path>` を処理する際、セッション保存に必要な RAM が足りない場合に、保存前の再構築可能なホスト側キャッシュを解放する動作を有効にします。既定では無効です。`--serve` 自体や SAVE を有効にするオプションではありません。`src/program/generate.cpp:746` `src/program/generate.cpp:906` `src/program/generate.cpp:12117-12146`

## 使い方

```sh
strata --serve --session-save-reclaim --pack MODEL-PACK
```

起動後、エンジンとの serve プロトコルへ `SAVE /path/to/session` を送ると、現在の会話を保存します。session file はリクエスト間で扱われ、`--prompt-cache > 0` などの条件も必要です。`src/program/generate.cpp:12054-12066` `src/program/generate.cpp:12094-12099`

## 値と既定値

- 値を取りません。parser はフラグを見つけると `session_save_reclaim = true` にします。初期値は `false` です。`src/program/generate.cpp:746` `src/program/generate.cpp:2639`
- 同じフラグを複数回指定しても true のままで、追加の効果はありません。引数位置に値を置く構文ではなく、その値は別の引数として処理されます（既知の別オプションの値でなければ未知引数エラーになります）。`src/program/generate.cpp:2416-2422` `src/program/generate.cpp:2639` `src/program/generate.cpp:2787-2792`
- 値の範囲検証はありません。フラグがない場合はキャッシュ解放を行わず、通常の SAVE 用 RAM 判定に進みます。`src/program/generate.cpp:12143-12146` `include/strata/core/session_save_reclaim.hpp:17-26`

## 実行時の動作

処理は `SAVE` の場合だけ実行され、`RESTORE` 側にはこのフラグを参照する分岐がありません。まず保存用のピーク RAM 必要量を見積もり、会話キャッシュに通常使う RAM の最低空き床（`--conversation-cache-min-free-mib`）を維持できるか確認します。既に条件を満たしていれば何も解放しません。`src/program/generate.cpp:12117-12146` `include/strata/core/session_save_reclaim.hpp:18-26`

不足している場合は次の順に処理します。

1. 会話キャッシュが再利用用に保持している K/V バッファを解放します。
2. pinned（固定）されていない退避済み会話を古いものから一件ずつ eviction し、各解放後に RAM 条件を再確認します。固定会話は残ります。
3. なお不足する場合、保存ファイルに選ばれる最深チェックポイントと pinned checkpoint を残し、それ以外を後ろから削除して各削除後に再確認します。

最深 checkpoint の選択とその格納領域は保持され、コピーを増やさない実装です。必要量や利用可能 RAM が不明な場合、または推定値がオーバーフローして必要量不明になる場合は、キャッシュ解放の根拠にしません。`include/strata/core/session_save_reclaim.hpp:13-50`

設定値との関係:

- 解放判定で維持する空き RAM 床は `--conversation-cache-min-free-mib`（既定 2560 MiB）です。`--session-min-free-mib`（既定 4096 MiB）はセッションファイルを書き込むディスク側の空き容量条件で、RAM の解放量を決めません。`src/program/generate.cpp:731` `src/program/generate.cpp:744-746` `src/program/generate.cpp:905-906` `src/program/generate.cpp:12143-12146` `src/program/generate.cpp:12185-12190`
- キャッシュを解放しても SAVE の RAM 事前判定が通らない場合は保存を拒否します。このオプションはメモリ確保の保証や上記 RAM 床の引き下げをしません。`src/program/generate.cpp:12157-12171`
- `--serve` を付けずに指定した場合、フラグ自体は parser に受理されますが、この分岐は `SAVE` 処理内にしかなく、解放処理は実行されません。`src/program/generate.cpp:2637-2639` `src/program/generate.cpp:12117-12146`

## 適用条件と副作用

- SAVE/RESTORE の共通前提として、path が空でないこと、layer split / peer device / batch を使っていないこと、`--prompt-cache > 0` であることが確認されます。違反時は session 操作が拒否されます。`src/program/generate.cpp:12094-12099`
- このオプションによって、再利用 K/V バッファ、未固定の退避会話、未選択の非 pinned checkpoint が失われることがあります。これらは再構築可能として扱われます。固定された会話・checkpoint と保存対象の最深 checkpoint は対象外です。`include/strata/core/session_save_reclaim.hpp:27-50`
- 解放が一件以上あれば標準エラーに、解放した checkpoint 数・退避会話数・ホストバイト数と「RAM を再確認する」旨が出ます。checkpoint の削除により、削除済み tail の長さが記録されていた場合は tail 記録も無効化されます。`src/program/generate.cpp:12147-12155`
- 索引では Qwen3.6 専用 parser を別スコープとしているため、この文書は通常の `src/program/generate.cpp` parser のオプションを扱います。Qwen3.6 専用 parser の挙動はここでは対象外です。`docs/cli/README.md:1130-1134` `docs/cli/README.md:1318-1322`

## 出力とエラー

- reclaim が何も解放しない場合、このオプション固有のログは出ません。解放があれば標準エラーに `strata serve: save reclaimed ...; checking RAM again` が出ます。`src/program/generate.cpp:12147-12155`
- 解放後も必要 RAM と空き床を満たさなければ、`session_save_checkpoints` が失敗理由を返し、SAVE は `SERR memory ...` を標準出力へ、`strata serve: session save <path>: ...` を標準エラーへ出してサーバーループを続けます。`src/program/generate.cpp:12069-12078` `src/program/generate.cpp:12157-12171`
- 保存成功時は標準エラーに保存概要、標準出力に `SAVED <tokens> <bytes> <ms>` が出ます。ディレクトリ flush 非対応時は、ファイル名が flush されない旨の警告が標準エラーに追加されます。`src/program/generate.cpp:12190-12204`
- オプション自体に値が欠けるケースはありません。未知の引数は usage と `unknown argument` を標準エラーへ出し、engine parser は終了コード2を返します。`src/program/generate.cpp:2787-2792`

## 根拠

- 既定値・help 表示・parser: `src/program/generate.cpp:746` `src/program/generate.cpp:905-906` `src/program/generate.cpp:2637-2640`
- SAVE/RESTORE の前提、RAM 事前判定、出力: `src/program/generate.cpp:12054-12099` `src/program/generate.cpp:12117-12204`
- 解放順、固定対象の扱い、RAM 再確認: `include/strata/core/session_save_reclaim.hpp:13-50`
- 文書の tool/command scope と予定リンク: `docs/cli/README.md:1128-1134` `docs/cli/README.md:1277-1280`。配置規約・調査基準: `docs/cli/001_investigation.md:13-35` `docs/cli/001_investigation.md:71-114`

調査時点の Strata checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main` で未コミット変更なしでした。同一 revision の既存 CLI `--help` と Release 配布物は確認していません。ソース parser と実装を根拠に記載しています。
