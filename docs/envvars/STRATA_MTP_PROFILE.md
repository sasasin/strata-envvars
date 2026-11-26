# `STRATA_MTP_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter の CUDA graph に GPU timestamp 用の stamp を挿入し、draft layer の各段階にかかった時間を集計して標準エラーへ出す測定用スイッチです。draft の計算・候補選択を切り替える設定ではありません。`MtpProf::stamp` は `on` と device buffer が有効な場合だけ stamp kernel を graph に追加し、段階名は `kMpNames` に定義されています（`engine/src/core/mtp.cpp:1018-1047`）。

読み取り自体は `mtp.cpp` のグローバル `g_mp` の構築時に行われます。測定処理は graph を使う CUDA/HIP 経路にあり、Metal の `draft()` は Metal drafter を呼び出して戻るため、この profiling graph を実行・集計しません（`engine/src/core/mtp.cpp:1028-1037, 1083, 1865-1883`）。

## 値と判定

`std::getenv` の戻り値が null でないことに加え、文字列の先頭 1 文字が `'1'` であることだけを調べます。数値変換、文字列全体の比較、空白の除去、大文字小文字の変換はありません（`engine/src/core/mtp.cpp:1035-1038`）。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 全 build（値判定） | off | `1`, `10`, `1anything` | 空文字、`0`, `01`, `true`, ` 1` |

未設定・空文字・先頭が `1` 以外なら `on=false` です。先頭が `1` なら後続文字列を検査せず `on=true` になります。読み取りはグローバル `g_mp` の初期化時に一度行い、その結果を `on` に保持します。プロセス実行中に環境を変更しても再評価しません（`engine/src/core/mtp.cpp:1028-1038,1083`）。CLI 引数や別の環境変数による上書きは、この設定の読み取り箇所にはありません（同 `mtp.cpp:1035-1038`）。

## 有効になる条件

- profiling 対象は `MtpDrafter::capture_round` / `capture_step` が作成する MTP round / step graph です。これらは `g_mp.init()` の後、各段階の記録中に stamp を追加します（`engine/src/core/mtp.cpp:1595-1603,1627-1655`）。
- `on=true` に加え、stamp 用 device buffer の確保が成功する必要があります。`cudaMalloc` に失敗すると `on=false` に戻し、CUDA error を取得して消費しますが、専用の警告やエラー行は出しません（`engine/src/core/mtp.cpp:1039-1043`）。
- graph capture の終了または graph exec の生成に失敗すると、その MTP capture は失敗します。共通処理は `mtp: <round/step> capture: <CUDA error>` を `err` に設定し、profile 専用の fallback はありません（`engine/src/core/mtp.cpp:1553-1566,1595-1631,1636-1656`）。
- 集計・profile 行の出力は `MtpDrafter::draft()` の `max_steps > 0` かつ `min_p <= 0.0f && !chain_rule_` ではない分岐に限られます。その fast path は graph を launch して同期しますが、`g_mp.collect()` を通らないため profile 行を出しません（`engine/src/core/mtp.cpp:1936-1973,2024-2048`）。
- Metal は `draft()` 内で `strata::metal_engine::mtp_draft()` を呼んで先に return するため、CUDA/HIP 用 `capture_round` / `capture_step` と `g_mp.collect()` を通りません。このファイルが Metal build にも含まれ、`g_mp` の構築時読み取りはありますが、Metal の MTP draft にこの測定は適用されません（`engine/metal/CMakeLists.txt:135-140`; `engine/src/core/mtp.cpp:81-91,1865-1883`）。

## 実行時の詳細

有効時、初回の round / step graph capture 前に `24 * 17 * 8` byte の device buffer を確保し、host 側にも同じ要素数の配列を用意します。round graph は index 0、step graph は 1–16 に割り当てられます。`record_front` / `record_rest` の処理段階境界と選択処理の後に stamp を記録し、graph に stamp kernel が加わります。capture は graph exec が既にある場合は再利用されるため、stamp 挿入も capture 済み graph に含まれます（`engine/src/core/mtp.cpp:1022-1027,1039-1047,1203-1204,1213-1227,1245,1293,1341-1355,1374,1437-1544,1595-1656`）。

集計する分岐では GPU 同期後に stamp 配列を host へコピーし、round と実行された step graph ごとに隣接 stamp の差を累積します。round graph の各段階時間と step graph の各段階時間を別々に保持し、300 round ごとに累積平均を出してカウンターをリセットします（`engine/src/core/mtp.cpp:1048-1062,1064-1080,2024-2048`）。

この機能は profiling stamp とその集計用であり、MTP のモデル状態や draft の選択条件を書き換える処理は含みません。一方、有効時は graph に stamp kernel を加えるため、測定対象 graph の実行内容と所要時間には計測処理が加わります（`engine/src/core/mtp.cpp:1045-1047,1203-1544`）。

## ログと測定値

集計対象があると、標準エラーに次の形式で round と step の各行を出します（段階名と数値部分は実行時に組み立て）。

```text
strata mtp profile (round, ms per graph over <件数>): <段階名> <ms> ... | total <ms>
strata mtp profile (step, ms per graph over <件数>): <段階名> <ms> ... | total <ms>
```

実際の固定書式は `strata mtp profile (%s, ms per graph over %lld):%s | total %.3f\n` です。集計データがない種類の行は出さず、未設定・無効値の場合や stamp buffer 確保失敗時も profile 行は出しません。fast path も集計処理を通らないため、この機能からの profile 行は出ません（`engine/src/core/mtp.cpp:1064-1080,1936-1973,2045-2048`）。この checkout の資料に本変数による測定結果はありません。

## 根拠

- `engine/src/core/mtp.cpp:1018-1083` — 用途、値の読み取り、buffer と profile state。
- `engine/src/core/mtp.cpp:1203-1549` — MTP graph 内の段階 stamp。
- `engine/src/core/mtp.cpp:1595-1656` — round / step graph capture と stamp 記録。
- `engine/src/core/mtp.cpp:1865-1883,1936-2048` — Metal 経路、draft の実行・集計条件。
- `engine/metal/CMakeLists.txt:135-140` — Metal build が `mtp.cpp` を含むこと。
