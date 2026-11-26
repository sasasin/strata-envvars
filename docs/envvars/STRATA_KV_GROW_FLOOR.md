# `STRATA_KV_GROW_FLOOR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

elastic K/V の拡張時に expert cache から K/V に譲る slot 数の下限を指定する。既定値は 128 slot。値を正の数にすると、K/V が cache の slot 範囲を使う際に cache が保持する下限がその数になる。下限に達した後も elastic K/V は新しい VRAM で拡張できるため、この変数は elastic K/V の有効化・無効化や K/V の最大 context を決めない。CUDA/HIP 共通 engine では `KvGrow::floor` と `kvg_ensure`、SYCL engine では同名の状態と処理に適用される（`engine/src/program/generate.cpp:11527-11536,11541-11559,11570-11595`; `engine/sycl/src/program/generate.cpp:6782-6790,6791-6805,6815-6837`）。

## 値と判定

両実装とも `std::getenv` で値を得て、ポインターが非 null であり `std::atoll(v) > 0` の場合だけ floor を上書きする。文字列全体の妥当性検査はなく、`atoll` が変換する先頭の数値部分が正なら採用される。したがって unset、空文字、`0`、負数、数値に変換できない文字列は既定値 128 のまま。`12tail` や先頭空白付きの ` 12` は変換結果が正なので 12 になる。`+12` も正の値として採用される。`true` は数値に変換できず採用されず、`0anything` は 0 なので採用されない。文字列全体の検査、大文字小文字判定、範囲 clamp はない（`engine/src/program/generate.cpp:11531-11532,11553`; `engine/sycl/src/program/generate.cpp:6785-6786,6799`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 共通 engine（CUDA/HIP）で cache からの拡張が可能 | 128 slot | `1`, `12tail`, `+12` | 空文字、`0`, `0anything`, `-1`, `true`, `abc` |
| SYCL engine で elastic K/V が有効 | 128 slot | `1`, `12tail`, `+12` | 空文字、`0`, `0anything`, `-1`, `true`, `abc` |

floor は `kvg_start` 内で読み取られる。関数内の `KvGrow` 状態であり `static` キャッシュではない。共通 engine では `kvg.from_cache` が true の場合にだけ環境変数を読むため、cache から slot を譲れない経路では値を読まず floor も動作に影響しない。SYCL は `kvg.on` が true なら floor を読み、その後 `kvg.from_cache` 相当の経路がない場合でも floor 値自体は記録されるが、cache の slot を譲る処理は行わない（`engine/src/program/generate.cpp:11541-11553`; `engine/sycl/src/program/generate.cpp:6791-6799`）。

## 有効になる条件

- `STRATA_KV_GROW_FLOOR` は elastic K/V の起動条件を満たした後の cache slot 下限にのみ作用する。elastic K/V は別途 `--kv-grow` または `STRATA_KV_GROW` で要求する。後者は空でない場合に先頭文字が `0` 以外なら有効、空または未設定なら CLI 値に従う（`engine/src/program/generate.cpp:3908-3909,7718-7726`; `engine/sycl/src/program/generate.cpp:1947-1948,4285-4293`）。
- CUDA/HIP 共通 engine と SYCL の両方で、起動には単一 GPU、全 K/V が VRAM にあること、expert profile、CPU から全 expert を読めること、expert cache が有効であること、VMM 対応などの条件が必要。`--batch`、`--vram-elastic`、`--peer-device`、複数 GPU、`--kv-resident`、remote cache 等の条件では要求されても無効になり、`strata generate: --kv-grow is off (one GPU, a profile, the whole K/V in VRAM, every expert in RAM, no --batch, --vram-elastic or --peer-device)` を stderr に出す（`engine/src/program/generate.cpp:7715-7729`; `engine/sycl/src/program/generate.cpp:4282-4296`）。
- `STRATA_KV_GROW_INIT` は elastic K/V の初期 cell 数を、`STRATA_KV_GROW_STEP` は拡張 cell 数の刻みを別々に制御する。いずれも正の `atoll` 結果のみ採用する。floor はこれらの値や `--max-context` を上書きしない（`engine/src/program/generate.cpp:7730-7732,11550-11553`; `engine/sycl/src/program/generate.cpp:4297-4299,6797-6799`）。
- 共通 engine では cache からの拡張可否がまず既定 floor 128 で判定され、環境値の読み取りはその後である。従って `top <= 128` で `from_cache` が false になった場合、floor を 128 未満に指定してもその実行で cache 拡張を有効にはできない。SYCL も `top > 128` を既定値で確認して `kvg.on` を決めてから floor を読み取るため、同じくこの変数だけでは開始判定を覆せない（`engine/include/strata/core/kv_grow_rules.hpp:23-31`; `engine/src/program/generate.cpp:11531,11541-11553`; `engine/sycl/src/program/generate.cpp:6785,6791-6799`）。
- env を読む箇所は CUDA/HIP 共通 engine と SYCL engine の `generate.cpp` に各 1 箇所ある。リポジトリ全体検索で見つかる `terminal/data/settings-register.json` の項目は設定登録データであり、実行時の値読み取りではない。

## 実行時の詳細

session の初期化後、生成経路で `kvg_start` が呼ばれるときに環境値を評価する。共通 engine は `kv_grow_start` が elastic K/V の pool を有効と判定すると `kvg.on` を設定し、VMM cache、residency table、expert source が揃い、loan の開始 slot `top` が既定 floor より大きい場合に cache から slot を使う経路に入る（`engine/include/strata/core/kv_grow_rules.hpp:23-31`; `engine/src/program/generate.cpp:11541-11553,13208`）。SYCL も elastic pool、cache VMM range、device/host residency、expert source、`top > 128` を要求する（`engine/sycl/src/program/generate.cpp:6791-6799,7666`）。

要求 cell 数が現在の割当を超えると `kvg_ensure` は必要量を計算し、cache から slot を譲れる経路では `kvg.lo > kvg.floor` の間、loan 範囲の下側から slot を空ける。熱い expert は loan 側のより冷たい slot に移し、空けた slot の VMM chunk を K/V に渡す。cache が floor に達するか、cache から必要量を得られない場合は新しい VRAM chunk で K/V を拡張する。floor を大きくすると cache に残す slot が増え、小さくするとより多くの slot を譲れる。ただし共通 engine では拡張時点で読み取った floor がその `KvGrow` 状態に保持され、後続の grow/trim 判定で使われる（`engine/src/program/generate.cpp:11570-11595,11655-11674,11678-11686`; `engine/sycl/src/program/generate.cpp:6815-6837,6927-6959,6963-6967`）。

環境値はプロセス起動時の一括 parse でも request ごとの static cache でもなく、`kvg_start` の実行時に読み取られる。コード内にこの変数を変更する処理はない。1 回の生成で floor が変えるのは cache/K/V 間の VRAM 配分であり、context 上限や生成 token の選択規則を変える処理は確認できない。

## ログと測定値

cache-backed elastic K/V の開始時には stderr に `strata generate: elastic K/V: ... the expert cache (%lld slots) gives the K/V room below slot %lld as the context grows` が出る。この行は floor の数値自体を表示しない。拡張時には `strata: K/V grown to ...` が出て、cache が譲った slot 数、新しい VRAM の有無、cache の resident slot 数を示す。拡張失敗時は `strata: the K/V could not grow to ...` を出して false を返し、生成呼び出し側では `return 1` となる（`engine/src/program/generate.cpp:11553-11559,11665-11674,24100-24102`; `engine/sycl/src/program/generate.cpp:6800-6805,6937-6959,13335-13338`）。floor 専用の警告・ログや測定値は確認できなかった。`docs/DETAILS.md:254` は `--kv-grow` の一般条件を説明しているが、この floor 環境変数の説明や値は記載していない。

## 根拠

- `engine/src/program/generate.cpp:7715-7732` — elastic K/V の有効条件、`STRATA_KV_GROW`・CLI 優先、初期 cell 設定。
- `engine/src/program/generate.cpp:11527-11559` — floor の既定値、cache 経路判定、環境値読み取りと開始ログ。
- `engine/src/program/generate.cpp:11563-11674` — 拡張時の floor 適用、cache slot の移動、拡張ログと失敗経路。
- `engine/sycl/src/program/generate.cpp:4282-4299` — SYCL 側の elastic K/V 有効条件。
- `engine/sycl/src/program/generate.cpp:6782-6805` — SYCL 側の floor の既定値、判定、環境値読み取りと開始ログ。
- `engine/sycl/src/program/generate.cpp:6809-6959` — 拡張時の floor 適用、cache slot の移動、拡張ログと失敗経路。
- `engine/include/strata/core/kv_grow_rules.hpp:23-36` — 共通 engine の elastic K/V / cache の開始条件と拡張 cell 計算。
- `docs/DETAILS.md:254` — `--kv-grow` の概要説明。floor 固有の記述なし。
