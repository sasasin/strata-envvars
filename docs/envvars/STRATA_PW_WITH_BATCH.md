# `STRATA_PW_WITH_BATCH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--batch` / `--slots` を指定したときに `--pipeline-windows` を一律に抑止する条件を外します。環境変数だけでは pipeline windows を有効にしません。pipeline windows が使える場合、サーバー内で単独処理になるリクエストの通常の solo path は windows の重なりを保ち、複数 slot をまとめる batch windows はその pipeline を使いません。変数の判定値は `batch_blocks_pw` を通じて自動設定・明示設定の両方の抑止判定に使われます。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は存在するが `e[0]` は `\0`） |
| 先頭文字が `1` の文字列 | 有効。`1`, `10`, `1anything` などを区別しない |
| その他 | 無効。`0`, `true`, ` 1` など |

文字列全体の比較や数値変換はせず、`getenv()` が非 null で先頭文字が `'1'` かだけを調べます。したがって値の範囲、後続文字、空白、大文字小文字の検査はありません。読み取りは generate の起動設定時に行い、ローカル `const bool` に保持します。この値はその generate 実行中に再読込されません。

根拠: `src/program/generate.cpp:5380-5384`。

## 有効になる条件

- `--pipeline-windows N`（`N` は 1 または 2）を指定するか、自動設定が pipeline windows を選ぶ必要があります。この変数単独では pipeline を有効化しません。CLI 値は `atoi` 後 0..2 に clamp され、未指定は内部値 `-1` です（`src/program/generate.cpp:959,3548`）。
- 実行経路は `--serve` の layer split です。各 stage が別 GPU にあり、少なくとも 2 stage が必要です。MTP drafter と `--spec >= 2` も必要です。明示設定では複数 GPU、stage 数、MTP、`--peer-device`、helper cache なども検査され、条件を満たさなければ stderr に `strata generate: --pipeline-windows ... is off: ...` を出して値を 0 にします（`src/program/generate.cpp:5409-5426`）。
- 自動設定（`--pipeline-windows` 未指定）は HIP だけで有効化候補になります。gfx12 の layer split では stage 数などを検査し、`STRATA_PIPELINE_AUTO=0`、MTP/spec 不足、batch 抑止、peer/helper cache、`--adapt-async` 等があれば無効です。CUDA 側のこの自動設定分岐は `on = false` です（`src/program/generate.cpp:5385-5407`）。
- `--batch` と別名 `--slots` は同じ `o.batch` を設定します。`o.batch != 0` なら既定で pipeline windows を抑止しますが、この環境変数が有効なら抑止されません（`src/program/generate.cpp:3486-3487,5384,5420`）。

この変数は Strata の `src/program/generate.cpp` にのみ実装されています。別実装 `sycl/src/program/generate.cpp` には名前の参照がなく、このコード経路による効果は確認できません。

## 実行時の詳細

設定判定は CLI 引数の読取後、stage や verifier のリソースを割り当てる前に行われます。環境変数は CLI の `--pipeline-windows` 値を上書きせず、`--batch` が pipeline を止めるかどうかだけに影響します。`--batch 1` や負数のように非ゼロの値も、この判定時点では `batch_blocks_pw` を立てます。batch 自体の検証は後で行われ、`--batch 1` は `--serve` の有効条件を満たさないため警告後に 0 へ戻されます。この順序のため、環境変数が無効なら、後から batch が無効化されても pipeline windows の抑止は戻りません（`src/program/generate.cpp:5384,6550-6556`）。

pipeline windows が成立した場合、実行側は stage ごとに二つの verifier を用意し、window の偶奇で使い分けて stage 間を重ねます。値 1 は prompt の verify windows、値 2 は decode windows も対象です。batch slot 側は別の batch window 処理を持ち、環境変数が有効でも batch windows に second verifier を使う処理にはなりません。`--batch` と共存して solo request の pipeline を保つ意図、および batch windows が pipeline を使わないことは実装コメントにも明記されています（`src/program/generate.cpp:5372-5379,10864-10890,14223-14239`）。

有効時は stderr に `strata generate: --pipeline-windows N stays on for the solo path beside M batch slots (STRATA_PW_WITH_BATCH=1); batch windows run without it` が出ます。無効時に batch が pipeline を止めた場合は `... is off: not with --batch slots (STRATA_PW_WITH_BATCH=1 keeps it for the solo path)` が出ます。pipeline 起動時は `strata serve: --pipeline-windows N: two verifiers per stage...` が出ます。stream 作成失敗はエラーを出して終了コード 1 で戻り、値 2 の decode 用 GDN snapshot を確保できない場合は stderr に理由を出し decode を serial にします（`src/program/generate.cpp:5420-5429,10877-10884,11297-11303,11318-11322`）。

## 根拠・資料との照合

候補名の全参照は `src/program/generate.cpp` の環境読取、判定利用とログ、および `docs/DETAILS.md` の表です。実際の読取は `std::getenv("STRATA_PW_WITH_BATCH")` の1箇所です。`docs/DETAILS.md:1088` は CUDA/HIP layer split、`--pipeline-windows 2` と batch slots の組合せとして説明し、2x RTX A6000 / IQ3_S の測定として solo request の code +14%、file rewrite +9%、long decode +3%、同時2 requestは遅くならず、2枚目の verifier が先頭 GPU に約270 MiBを使うと記載しています。これらは資料記載の測定値であり、他の条件での性能を示すものではありません。
