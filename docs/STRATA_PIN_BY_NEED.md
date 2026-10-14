# `STRATA_PIN_BY_NEED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

通常の resident arena では、GPU から DMA できるように arena の先頭から連続範囲を登録します。この方式は、GPU が保持するエキスパートの分布に関係なく先頭側を優先します。`STRATA_PIN_BY_NEED` を有効にすると、`--expert-profile` の順位と GPU エキスパートキャッシュの推定内容から登録候補を作り、GPU に常駐しない見込みの高順位エキスパートから個別の範囲として host pin します。ピンできなかった領域は、可能な場合 OS の working-set lock で常駐させます。

これは起動時に arena を作る経路の設定で、生成時にエキスパートの選択やモデル出力を変更する機能ではありません。直接の環境変数読み取りは `src/program/generate.cpp` の resident arena 初期化箇所一つです。

## 値と判定

`std::getenv()` の戻り値が存在し、先頭文字が NUL でも `'0'` でもなければ有効です。文字列全体の parse、数値変換、大文字小文字変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。先頭からの従来 pinning を使用 |
| 空文字 | 無効（`pn[0] == '\0'`） |
| `0`、`0anything` | 無効（先頭が `'0'`） |
| `1`、`true`、`false`、空白で始まる文字列など | 有効（空でなく先頭が `'0'` 以外） |

従って `=1` だけが有効値ではありません。`false` もコード上は有効です。

併用する `STRATA_PIN_BY_NEED_SKIP` は、空でないとき `std::atoll()` で変換されます。負値は 0 に丸め、結果は profile の件数を上限にします。数値として読めない文字列は `atoll` の結果 0 です。未設定または空文字なら自動推定を使います。これは本変数の有効化条件ではなく、GPU に常駐すると見積もる ranked pair の件数を指定します（`src/program/generate.cpp:4938-4969`）。

## 有効になる条件

次の条件が必要です。

- `--mmap-experts` の FileExpertSource 経路ではなく、resident arena を使う。
- `--expert-profile` が読み込まれ、ランキングが空でない。
- 単一 GPU で、layer split／peer GPU を使わない。
- 他 GPU 上の helper expert cache がない。

profile が空、複数 GPU／peer GPU、または helper cache がある場合、stderr に `strata generate: pin by need: off (%s); the prefix pinning stays` という理由付きログが出て、従来方式に戻ります。profile がない理由は `it needs --expert-profile (the ranking)`、GPU 構成の理由は `not with a layer split or a peer GPU`、helper cache の理由は `not with helper caches on other GPUs` です（`src/program/generate.cpp:4929-4936`）。

`STRATA_ARENA_MMAP` が arena の file-backed mmap を選ぶ場合と `--shared-expert-arena` を使う場合も、`ArenaExpertSource::open()` は padded layout／by-need 登録を作りません。呼び出し側はその前に優先順位を設定し、候補数のログを出すことがありますが、この二つの arena 方式では登録順を by-need に切り替える結果にはなりません（`src/core/expert_source.cpp:4510-4519,4595-4602`）。

## 実行時の詳細

環境変数は `generate` の arena 初期化中、arena の `open()` より前に読みます。profile はそれ以前に `--expert-profile` から読み込まれます。設定はその起動処理で一度判定され、リクエストごとには読み直されません（`src/program/generate.cpp:3656-3699,4927-4990`）。

GPU に常駐すると見積もる順位数 `skip` は、`STRATA_PIN_BY_NEED_SKIP` がなければ `--expert-cache` の明示スロット数、または空き VRAM から予約量を差し引いた値を基に算出されます。推定バイト数は 2% 減らし、profile の順位順に収まる pair 数を数えます。続いて pin 候補は、profile の `skip` 位以降、profile にない全 pair（layer/expert 順）、最後に GPU 常駐見込みの上位 `skip` pair の順です。最初の二群が非常駐見込みの候補として別カウントされ、pin 上限が余れば最後の群も対象になります（`src/program/generate.cpp:4938-4986`）。この推定は実際の後続 GPU cache 初期化より前に行われます。

`ArenaExpertSource` は by-need layout の場合、各 expert blob の stride を 4 KiB 境界に切り上げ、候補の隣接 blob を結合して登録範囲を作ります。stride 分の arena 増加があります。登録は優先順位順で、4 KiB ページの内側に合わせて行い、先行範囲と重なるページを除外します。`STRATA_ARENA_PIN_GIB` または呼び出し側の上限に達したとき、あるいは CUDA/HIP runtime の host registration が失敗したとき、後続の登録を止めます。未登録の穴は `STRATA_ARENA_LOCK=0` でなければ resident lock の対象になります（`src/core/expert_source.cpp:4595-4643`; `src/core/pinned.cu:502-586`）。

登録後、各範囲の device alias を取得します。失敗すると by-need の alias 表を破棄して pin 済みバイト数を 0 とし、正しい device pointer を使えない経路を避けます。成功時は blob 全体が一つの登録範囲内にある場合だけ `pinned()`／`device_alias()` が pin 済みと判定し、layer に PCIe 経由で利用可能な blob があるかも範囲から作ります（`src/core/expert_source.cpp:4752-4778,4852-4884`）。

主な stderr 出力は、有効経路の候補・profile 件数、登録範囲数、pin されたバイト数と非常駐候補に対する割合です（`src/program/generate.cpp:4983-5009`）。この設定だけで pin 上限を増やすことはありません。特に Windows では `STRATA_ARENA_PIN_GIB` の既定上限が適用されます。Linux では同じ候補選択ロジックでも登録可能量は runtime／ドライバーの結果に依存します。

## 文書・測定値との照合

`docs/DETAILS.md:188-194` は本機能を opt-in、単一 GPU の arena 向けとして説明し、Windows の WDDM 共有予算により prefix pinning では後半層に PCIe share がなくなる例と、ranked non-GPU-resident expert を優先する動作を記しています。ソースにも単一 GPU・profile 前提および順位付き候補登録が確認できます。README 日本語版は Windows の prompt read が RTX 5070 で +4.4% と記載します（`README.ja.md:168-180`）。DETAILS の community report は RTX 3090 + Ryzen 5 5600X、prompt read +5–7%（56K–117K tokens）等を報告しています。いずれもリポジトリ記載の測定値であり、この調査で再測定した値ではありません。一般的な性能向上を保証するものではありません。

## 根拠

- `src/program/generate.cpp:3656-3699`: expert profile の読込。
- `src/program/generate.cpp:4902-4916,4927-5009`: resident arena 経路、環境値判定、条件、候補順位とログ。
- `include/strata/core/expert_source.hpp:952-964`: 優先順位 API と呼び出し前提。
- `src/core/expert_source.cpp:4510-4519,4595-4643,4752-4778,4852-4884`: mmap 除外、padded layout、範囲作成、alias と pinned 判定。
- `src/core/pinned.cu:502-586`: 範囲ごとの登録、上限・失敗時の停止、未登録範囲の resident lock。
- `docs/DETAILS.md:188-194`, `README.ja.md:168-180`: 公開説明と測定値。
