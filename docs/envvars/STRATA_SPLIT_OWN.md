# `STRATA_SPLIT_OWN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU 間の layer split において、各 stage の prompt path が expert cache の末尾を借りる代わりに、自前の prompt buffer を保持するかを選びます。自前 buffer は各カードの VRAM を消費し、cache に置ける expert 数も減らし得ます。環境変数が有効になった場合、Strata は `o.no_prefill_borrow` を立て、split の容量見積もりにも buffer 用 reserve を反映します（`engine/src/program/generate.cpp:4895-4952,6821-6832`、SYCL は `engine/sycl/src/program/generate.cpp:2353-2420,3844-3860`）。ソースコメントは、expert cache の保持内容が変わる全 expert 保持時には既定の借用経路と出力が異なると記しています（同 `:4916-4918`、SYCL `:2375-2377`）。

この変数を読む実装は CUDA/HIP 系 `engine/src/program/generate.cpp` と SYCL 系 `engine/sycl/src/program/generate.cpp` の各1箇所です。どちらも `--serve` を必要とする multi-GPU layer split の処理内にあり、単一 GPU の通常実行では参照されません（同 `:4786-4856`、SYCL `:2266-2334`）。

## 値と判定

値は数値や真偽値として parse せず、文字列ポインタの有無・先頭文字・`auto` との完全一致で判定します。

| 設定値 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv` が `nullptr` | この分岐は何もせず、既定の借用経路を保つ |
| 空文字 | 設定ありだが先頭文字が `\0`。`auto` でなく、`'1'` でもない | 何もせず、借用経路 |
| `0` または `0anything` | 先頭文字が `'0'` | 外側の条件で無効。借用経路 |
| 完全に `auto` | `std::string(own_env) == "auto"` | 全 stage の VRAM を調べ、後述の12%条件を満たせば自前 buffer |
| `1` または `1anything` | `auto` ではなく先頭文字が `'1'` | 容量の12%判定をせず自前 buffer を選ぶ |
| その他（例: `2`, `true`, `false`, `AUTO`, ` auto`, `auto `） | `auto` と完全一致せず、先頭文字も `'1'` でない | 何もせず、借用経路 |

大文字小文字、空白、後続文字の妥当性検査はありません。従って `10` や `1junk` も有効扱いですが、`0anything` は無効扱いです。`auto` は完全一致のみです（`engine/src/program/generate.cpp:4921-4924`、`engine/sycl/src/program/generate.cpp:2380-2383`）。

## 有効になる条件

- `--layer-split` が指定され、複数 GPU に分割される必要があります。layer split の引数検証は `--serve` を要求します。split が無効、または自動 split で利用可能な別 GPU がなく単一 GPU に戻る場合、この環境変数の読み取りブロックには入りません（`engine/src/program/generate.cpp:4786-4856`、`engine/sycl/src/program/generate.cpp:2266-2334`）。
- split には `--expert-profile` が必要です。未指定なら `strata generate: a layer split across GPUs needs --expert-profile` を stderr に出し、終了コード `2` で戻ります（`engine/src/program/generate.cpp:4895-4899`、`engine/sycl/src/program/generate.cpp:2353-2358`）。
- `--no-prefill-borrow` が有効なら環境変数の分岐を飛ばします。SYCL 実装には反対向きの `--prefill-borrow` もあり、これで借用設定に戻すと環境変数を評価する条件に入れます（`engine/src/program/generate.cpp:4035,4922`、`engine/sycl/src/program/generate.cpp:2030-2031,2381`）。
- `--split-skip-if-fits` も環境変数を評価しない条件です。これは `--layer-split auto` のとき CUDA0 だけで足りるか調べるための指定で、split を維持するときもこの環境変数による自前 buffer 選択は行いません（`engine/src/program/generate.cpp:4922,6446-6490`、`engine/sycl/src/program/generate.cpp:2381,3522-3580`）。
- `auto` は CUDA/HIP 側または SYCL 側で primary device 0 と全 split device のメモリ容量を取得し、それぞれで `reserve_mib * 100 <= 12 * total_mib` の場合にだけ自前 buffer を選びます。容量取得失敗時は自前 buffer を選びません。reserve は `160 + (own_chunk * 680) / 1024 + 96 * 4` MiB、`own_chunk` は `--prefill auto` または非正の chunk なら2048、それ以外は `--prefill` の chunk 値です（`engine/src/program/generate.cpp:4925-4941`、`engine/sycl/src/program/generate.cpp:2384-2409`）。
- `1` 系の値は上記12%判定をしません。実際の割り当てが足りることまでは保証せず、起動後に容量不足で chunk の縮小や起動失敗になることがあります（`engine/src/program/generate.cpp:13047-13137`）。
- `--prefill` は reserve の見積額に影響します。自前 buffer が選択されると `o.no_prefill_borrow` が立ち、`--prefill auto` は後段で自動設定を解除し、既定では2048-token chunkになります（`engine/src/program/generate.cpp:4925-4945,4990-4995`、SYCL `:2384-2412,2500-2503`）。
- `STRATA_SPLIT_OWN_PLACE=reserve` は別の設定で、自動 split の配置探索にも prompt buffer reserve を含めます。この指定がない場合、`split_own_auto` によって探索時の reserve を0にし、自前 buffer 選択後の cache 容量減少を split 境界選択に反映しません（`engine/src/program/generate.cpp:3880-3913`、SYCL `:3880-3913`）。

## 実行時の詳細

環境変数は split 構成を作る段階で `std::getenv` により1回読みます。関数 static への保存やリクエストごとの再読込はありません。値に応じて `o.no_prefill_borrow = true` と `split_own_auto = true` にし、後続の split sizing と prompt path 初期化へ設定を渡します（`engine/src/program/generate.cpp:4921-4945,6821-6832`、SYCL `:2380-2412,3844-3860`）。この実行中に環境値を変えても、既に選んだ分岐には反映されません。

自前 buffer を選ぶと各 stage の cache 末尾から prompt buffer 用 slot を借りず、prompt path が自身の buffer を確保します。split の VRAM 見積もりでは、prefill chunk と ring に応じた reserve を差し引きます（`engine/src/program/generate.cpp:6815-6832`、SYCL `:3844-3860`）。serve 起動時の実割り当てでは容量を確認し、`--prefill auto` は小さい chunk に fallback します。明示 chunk も複数候補へ段階的に縮小して再初期化し、それでも初期化できなければ理由を stderr に出して終了コード `1` で戻ります（`engine/src/program/generate.cpp:13047-13137`）。

## ログと測定値

- 自前 buffer を選ぶと `strata generate: layer split: every stage keeps its own prompt buffers (~%lld MiB each, %lld-token chunks)` を stderr に出します。値が `auto` 以外で自前 buffer になった場合は末尾に ` (STRATA_SPLIT_OWN=1)` が付きます（`engine/src/program/generate.cpp:4943-4948`、SYCL `:2410-2415`）。
- `auto` が12%条件を超えた場合は、最初に超えた GPU について `strata generate: layer split: the prompt paths borrow from the caches (%s)` を出します。容量取得失敗時や、未設定・無効値ではこの分岐からの説明ログはありません（同 `:4929-4951`、SYCL `:2388-2418`）。
- `docs/MULTI_GPU.md:147,292` も `1` と `auto`、12%条件、および R9700 + RX 9070 XT の計測値を記載しています。前者の仕様は実装と一致します。計測値は同資料の記録であり、ここでは他の構成への性能保証として扱いません。

## 根拠

- CUDA/HIP 系の値判定・ログ: `engine/src/program/generate.cpp:4921-4952`
- SYCL 系の値判定・ログ: `engine/sycl/src/program/generate.cpp:2380-2420`
- layer split の serve 条件、profile 要求: `engine/src/program/generate.cpp:4786-4856,4895-4899`; SYCL `engine/sycl/src/program/generate.cpp:2266-2334,2353-2358`
- CLI 優先条件と split skip: `engine/src/program/generate.cpp:4035,4922,6446-6490`; SYCL `engine/sycl/src/program/generate.cpp:2030-2031,2381,3522-3580`
- buffer reserve と起動時の縮小・失敗経路: `engine/src/program/generate.cpp:6815-6832,13047-13137`; SYCL `engine/sycl/src/program/generate.cpp:3844-3860`
