# `STRATA_SPLIT_COVER_B`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部依存の環境変数動作は対象外。

## 役割

`--serve --layer-split auto` の複数 GPU 配置探索で、expert profile の順位から各 expert の予測 routed mass を作る coverage curve の指数 `b` を指定します。探索はこの mass を使って各候補配置の expert cache hit 率と予測 decode window 時間を比較し、layer 境界を決めます。CUDA と SYCL に実装があります。

`STRATA_SPLIT_COVER_B` が設定されていると、2 GPU・3 GPU でも従来の順位べき乗則ではなく coverage curve を使うため、指数値だけでなく探索モデルそのものも切り替えます。4 GPU 以上では変数が未設定でも coverage curve が使われます。

## 値と判定

| 状態 | `b` | coverage curve の選択 |
|---|---:|---|
| 未設定 | `3.0` | 2・3 GPU では旧式の `(r+1)^-1.2`。4 GPU 以上では coverage curve |
| 設定あり | `std::atof()` の結果 | GPU 数にかかわらず coverage curve |

設定値は文字列全体の検証なしに `std::atof()` で `double` に変換されます。したがって、`2.5` は `2.5`、`2.5tail` は先頭の数値部分 `2.5`、空文字や数値に変換できない文字列は `0` になります。空文字でも環境変数自体は設定済みなので、2・3 GPU で curve を選ぶ条件が成立します。値の範囲検査や clamp はありません。負値、ゼロ、非常に大きな値、`atof()` が受理する非有限値を設定した場合もそのまま式へ渡され、意図した coverage になる保証はコードにありません。

curve は profile 件数を `N`、順位を `r`（0 始まり）として、各順位の mass を

`(1 - r/N)^b - (1 - (r+1)/N)^b`

で求めます。これは prefix の held fraction `f` に対して `H(f)=1-(1-f)^b` とする配分です。4 GPU 以上で未設定なら `b=3.0` が使われます。2・3 GPU で未設定の旧式では順位ごとに `(r+1)^-1.2` を使います。

根拠: CUDA `src/program/generate.cpp:3754-3769`、SYCL `sycl/src/program/generate.cpp:3588-3603`。

## 有効になる条件

- `--serve` で `--layer-split auto` を指定し、複数 GPU の split が成立している必要があります。1 GPU しか見えない場合、コードは `--layer-split auto` を解除します。
- 配置探索へ入る条件は `multi_gpu && split_auto` です。固定境界の `--layer-split K[,K2...]` では、この読み取り箇所による効果はありません。
- auto split の探索内で expert profile の順位表が mass の入力になります。profile が空なら順位ごとの mass は作られず、この変数が profile を生成したり実測 routing 頻度を読み込んだりする処理もありません。
- その他の探索条件（VRAM 容量、各 stage の layer range、profile 順位、miss cost など）は独立して残り、環境変数はその評価を使う配置探索の予測 mass を変えるものです。

根拠: CUDA `src/program/generate.cpp:2299-2348,3692-3695`、SYCL `sycl/src/program/generate.cpp:3537-3541`。

## 実行時の詳細

CUDA/SYCL それぞれの `generate.cpp` で、auto split の探索に入った後に `getenv()` で値を取得します。プロセス起動時に一度だけ保存する `static` 変数ではなく、その探索処理で読みます。コードにリクエストごとの再読込はなく、ここで決めた mass 配列がその配置探索の候補評価に使われます。

候補配置では、profile の各 rank を担当 stage に割り当て、各 stage の cache 容量に入る expert の mass を合計します。未 cache の mass は `STRATA_SPLIT_MISS_MS` および stage ごとの link scale と組み合わされ、layer 処理時間と合わせた予測時間になります。最終的な選択結果は `layer split auto: K=... - predicted ... ms per decode window; the caches ...` の stderr 行に出ます。このログは予測値であり、実測性能を示すものではありません。

CUDA と SYCL の該当する値変換、curve 選択、順位式は同じです。CUDA の探索評価は `generate.cpp:3797-3815`、選択ログは `generate.cpp:4165-4167` にあります。SYCL では profile mass を評価する箇所が `sycl/src/program/generate.cpp:3623-3639` です。

## 文書・測定との照合

`docs/DETAILS.md` を確認しましたが、この変数の利用者向け説明や、この指数を変更した場合の測定結果は見つかりませんでした。`generate.cpp` 内の設計コメントは、既定 `b=3` の選択理由や過去の複数環境での hit-rate 比較を記していますが、その記述だけから任意のモデルやハードウェアでの効果を一般化することはできません。ここでは測定値を主張しません。

## 根拠

- CUDA 側の `b` の既定値、変換、coverage curve の選択と式: `src/program/generate.cpp:3752-3769`
- CUDA 側の held mass / 予測時間への反映: `src/program/generate.cpp:3797-3815`
- CUDA 側の探索条件と結果ログ: `src/program/generate.cpp:3692-3695,4165-4167`
- CUDA 側の `--serve`、`--layer-split auto`、GPU 数による split 条件: `src/program/generate.cpp:2299-2348`
- SYCL 側の同じ `b` 判定・coverage curve の式: `sycl/src/program/generate.cpp:3586-3603`
- SYCL 側の mass による候補予測: `sycl/src/program/generate.cpp:3623-3639`
