# `STRATA_KV_GROW_HOLD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` のリクエスト切り替え時に、弾性 K/V を現在のリクエストに必要な大きさまで縮める代わりに、会話キャッシュ内で最長の parked conversation を復元できる大きさまで保持する opt-in 変数。保持対象は K/V の割り当てであり、会話の保存・選択・復元自体を有効化する設定ではない。値を読むのは `engine/src/program/generate.cpp` のサーバー側 `kvg_trim` 呼び出しだけである（同ファイル:20066-20070、サーバー処理の入口:12302）。

## 値と判定

関数内 `static const bool` の初期化で `std::getenv` を一度呼び、未設定でなく、かつ `std::atoi(v) != 0` なら有効とする。文字列全体の厳密な数値検証はなく、`atoi` が先頭の整数部分として変換する。空文字や数字で始まらない文字列は `atoi` が 0 を返す。整数の後ろの文字は判定されず、変換範囲外の値について実装の保証はない。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `--serve` 内で `kvg.on` の処理に到達 | 無効（`hold_on=false`） | `1`, `-1`, `2tail` | 空文字, `0`, `0anything`, `true`, `false`, ` 0x` |

この設定は `kvg.on` の場合に初めて評価される `static` 値なので、その後のリクエストや実行中の環境変数変更では再読込されない。未設定時は hold なしとなる（同ファイル:20066-20070）。

## 有効になる条件

- `--serve` のリクエスト処理を通ること。同ファイルのこの読み取り箇所は `if (o.serve)` 内にある（同ファイル:12302、20066-20070）。
- 弾性 K/V (`kvg.on`) が有効であること。起動側では `STRATA_KV_GROW` が空でなければその先頭文字が `0` かどうかで `--kv-grow` / `--no-kv-grow` の選択を上書きし、未設定または空文字なら CLI の最終設定を使う。要求されると単一 GPU、K/V 全体が VRAM、expert profile 使用、CPU-resident experts 無効、expert cache 有効、remote expert 無効、VMM 利用可能、`--batch` なし、`--vram-elastic` なし、`--peer-device` なしを要求する。要求されても条件が合わない場合は `strata generate: --kv-grow is off (...)` を stderr に出す（同ファイル:3908-3909、7715-7729）。セッションの QSA K/V pool が elastic として初期化されていない場合も `kvg.on` は false になる（同ファイル:7730-7732、11541-11549、`engine/include/strata/core/kv_grow_rules.hpp`:26-31）。HIP では `STRATA_HIP_VMM` の先頭文字が `0` だと VMM 初期化を止めるため、この条件を満たさず弾性 K/V は有効にならない（`engine/src/core/vmm.cpp`:188-215）。
- 実際に parked conversation 分を上乗せして trim するには `kvg.from_cache` も必要。これは elastic pool に加えて VMM expert-cache range、device/host residency table、expert source があり、利用可能な slot top が floor を超える場合に限られる。それ以外でも弾性 K/V は新しい VRAM で成長し得るが、`kvg_trim` は早期 return するため、この変数による保持指定は働かない（`engine/src/program/generate.cpp`:11541-11549、11678-11680、`engine/include/strata/core/kv_grow_rules.hpp`:23-31）。
- parked conversation が存在しない場合、`longest_tokens()` は 0 を返すため、この設定による追加保持分はない（`engine/include/strata/core/conversation_cache.hpp`:325-330）。会話キャッシュの有効化や容量は別設定による。
- ソース上の読み取りは CUDA/HIP 側の `engine/src/program/generate.cpp` にあり、SYCL の別実装 `engine/sycl/src/program/generate.cpp` と Metal の実装にはこの名前の読み取りがない。設定一覧も対象を NVIDIA / AMD としている（`docs/SETTINGS.md`:149）。

## 実行時の詳細

サーバーは次のリクエストに移る前に、elastic K/V が有効なら device を静止させてから `kvg_trim(n + 256, hold)` を呼ぶ。`hold_on` が false なら `hold=0`、true なら `conversations.longest_tokens() + 256` である。`kvg_trim` は `max(n + 256, hold)` を次の K/V 必要量とし、`kvg.step` 単位へ切り上げて縮小する。step の既定は 8192 cells で、正の `STRATA_KV_GROW_STEP` があれば置き換わる。したがって hold 有効時は最長 parked conversation の K/V が次の短いリクエストの間も残り、無効時は次リクエスト相当まで縮める（`engine/src/program/generate.cpp`:20063-20070、11527-11535、11550-11553、11676-11687）。

trim は現在の K/V が目標より少なくとも `2 * step` 大きく、かつ expert-cache から貸与された範囲が残っている場合に実行される。それ以外は成功扱いで何も縮めない。実 trim では K/V の余剰分を expert cache に返し、profile の expert を再充填する。parked conversation の token、生成 token 選択、会話 cache の park / eviction 条件をこの変数が変更する処理はない（同ファイル:11678-11744、`engine/include/strata/core/conversation_cache.hpp`:325-330）。

`kvg_trim` の失敗時は `ERR the K/V could not give its VRAM back to the expert cache` を stdout に出して flush し、そのサーバー処理は status 1 で戻る。実 trim は stderr に `strata: K/V trimmed to ...` を出す。expert cache の VRAM を返せない場合は `strata: the expert cache could not take its VRAM back from the K/V`、再充填の同期失敗なら `strata: refilling the expert cache failed: ...` も出る。trim を見送るだけの経路ではこの trim 成功ログは出ない（同ファイル:20070-20074、11691-11702、11732-11744）。

## ログと測定値

この変数専用の有効・無効ログはない。実際に縮小した場合の `strata: K/V trimmed to ...` と、サーバー終了経路のエラーは「実行時の詳細」に記載した。`docs/DETAILS.md` は弾性 K/V (`--kv-grow`) の条件と測定を記載するが、この hold 設定の測定値は見つからなかった（`docs/DETAILS.md`:254、1626）。

## 根拠

- `engine/src/program/generate.cpp:20063-20074` — 読み取り、static cache、trim 呼び出し、失敗時の終了。
- `engine/src/program/generate.cpp:7715-7732` — 弾性 K/V を要求する CLI / env と有効条件。
- `engine/src/program/generate.cpp:11527-11560` — elastic 状態、growth step、`kvg_start`。
- `engine/src/program/generate.cpp:11676-11744` — hold 値の反映、trim とログ・失敗処理。
- `engine/src/core/vmm.cpp:188-215` — HIP の VMM 可否と `STRATA_HIP_VMM`。
- `engine/include/strata/core/kv_grow_rules.hpp:18-31` — pool と cache 条件による elastic / cache-backed 状態。
- `engine/include/strata/core/conversation_cache.hpp:325-330` — 最長 parked conversation の token 数。
- `docs/SETTINGS.md:149`、`docs/DETAILS.md:254,1626` — 設定一覧と関連する弾性 K/V の説明。
