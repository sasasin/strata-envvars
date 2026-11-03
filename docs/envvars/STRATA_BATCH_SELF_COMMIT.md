# `STRATA_BATCH_SELF_COMMIT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

batch verifier の window が各 slot から 1 行ずつを処理するとき、GDN の畳み込み履歴と recurrent state を window 自身で進めます。その window の後に全行を確定する commit graph を起動しません。対象は `--batch` による複数 slot の window で、通常の単独生成を一律に変える設定ではありません。

## 値と判定

`src/core/verify.cpp` の `env_on()` は環境変数を `getenv()` で読み、値が存在し、空文字でなく、先頭文字が `0` でなければ ON とします。文字列全体の parse はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF。ただし後述の Windows gfx1151 batch 既定が設定する場合がある |
| 空文字 | OFF |
| `0` または `0` で始まる文字列 | OFF（例: `0`, `0abc`） |
| その他の非空文字列 | ON（例: `1`, `2`, `true`, `false`, `off`） |

したがって `=false` や `=off` も ON です。数値変換、範囲検査、大文字小文字の正規化はありません。環境値そのものに CLI 引数による上書きはありませんが、`--batch` などが batch verifier を使う条件を決めます。

## 有効になる条件

- `--batch` 等で batch verifier が構成され、処理中の window が batch recurrence 経路を使うこと。
- window の row-slot 対応が重複しないこと（1 slot あたり 1 row）。行が同じ slot の draft/proposal を複数含む場合、この設定による self-commit は使いません。
- batch window 内の GDN layer では、conv 履歴と GDN state を window graph 内で更新します。QSA indexer tail の snapshot も省きます。条件を満たさない window では通常の commit graph 経路に戻ります。

この設定は `STRATA_PIPED_MTP` と併用できません。`STRATA_PIPED_MTP` が空でなく先頭文字 `0` 以外なら、生成側は `STRATA_BATCH_SELF_COMMIT` が空でなく先頭 `0` 以外かを調べ、ON のとき piped MTP を無効化して stderr に警告します。`STRATA_BATCH_SELF_COMMIT` が未設定・空・`0...` なら、この競合理由では piped MTP を止めません（他の batch/group/window 条件は別途適用されます）。

## 実行時の詳細

Verifier は `batch_self_commit_on()` の初回呼び出しで値を読み、function-local `static const bool` に cache します。ソース注釈によれば、これは起動直後ではなく初回利用時に読むためです。AMD HIP gfx1151 の Windows batch 既定を `main()` が設定した後に値を確認でき、判定後の環境変更は反映されません。

Windows の gfx1151（Strix Halo）では、batch slot が 2 以上で `STRATA_GFX1151_DEFAULTS=0` でない場合、arch defaults がこの変数を `1` に設定します。既に環境変数が存在すれば値を変更しません（空文字も「設定済み」として保持されます）。この既定値は HIP build の device 初期化経路で `apply_arch_defaults()` から適用されます。

また `serve/server.py` は Linux 上の複数 slot 構成で、DeepSeek・SYCL・Metal・Vulkan と HIP を除く engine に並列 stack 環境を `setdefault` で追加します。このため Linux CUDA Qwen の `--batch`/parallel が 2 以上なら、設定や継承環境が先に値を与えていないと子 engine に `STRATA_BATCH_SELF_COMMIT=1` が渡ります。サーバー設定の `env` に明示した値はそのまま残ります。

setup の profile も `env` に `1` を補う場合があります。replica profile は opt-in（`STRATA_REPLICA_PROFILE` または run config）で、対応する Qwen3.8 quant、2 枚以上の GPU と VRAM/RAM 条件などを満たしたとき適用されます。4-card AMD profile は R9700 4 枚・Qwen3.8 IQ3_S 等の条件を満たし、profile を無効化していない場合に適用されます。どちらも既存の process 環境に変数があれば profile は env 値を補わず、config の env に値があれば `setdefault` により保持します。

Verifier 初期化時、判定値が ON なら stderr の `strata verify: batch windows ...` に `, one-row windows keep their rows` が付きます。これはスイッチが ON であることの表示で、各 window が実際に一意な row-slot 構成かどうかの表示ではありません。実際の省略判定は window ごとに行い、対象外なら commit graph を通常通り起動します。piped MTP との競合時の警告は `strata generate: WARNING: STRATA_PIPED_MTP is off: it does not combine with STRATA_BATCH_SELF_COMMIT (the window would keep its rows itself)` です。

## 根拠

- `src/core/verify.cpp:308-311,322-330`: `env_on()` の値判定、初回使用時の static cache と理由。
- `src/core/verify.cpp:338-345,1411-1415`: 一行一 slot の条件と batch window の `keep_rows` 判定。
- `src/core/verify.cpp:1717-1718,1764-1769,1871-1877`: GDN conv/state 更新と indexer tail snapshot の条件。
- `src/core/verify.cpp:3972-3978,4014-4016,4816-4822,4924-4927`: 初期化ログ、commit graph capture/launch の省略箇所と通常 commit error path.
- `src/program/generate.cpp:3702-3719`: HIP device 情報取得後の arch defaults 適用。
- `src/core/arch_defaults.cpp:193-209,221-229,283-298`: Windows gfx1151・2 batch slots 以上の既定値、既存値を尊重する設定処理とログ。
- `src/program/generate.cpp:6653-6678`: `STRATA_PIPED_MTP` との競合判定と stderr 警告。
- `serve/server.py:3974-3983,4009-4019,4054-4071`: Linux server parallel stack の値と適用条件、子 engine 環境の構成。
- `strata_control/replica_profile.py:37-39,44-49,77-99,102-122` と `setup.py:10863-10877`: opt-in replica profile の条件と値の注入。
- `strata_control/amd_four_card.py:1-14,27,34-61,64-91` と `setup.py:10878-10885`: 4-card AMD profile の条件と値の注入。
- `docs/BATCHING.md:110-123,492-495,576-593`: opt-in switch の説明、piped MTP の制約、4x R9700 serving profile での利用例。測定値は同文書の特定構成に限られ、この変数単体の一般的な性能効果を示すものではありません。
