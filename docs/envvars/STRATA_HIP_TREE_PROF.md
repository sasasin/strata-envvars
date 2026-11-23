# `STRATA_HIP_TREE_PROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

この変数は、HIP backend の DSpark adaptive beam tree speculative step に HIP event による計測と stderr の計測行を有効にします。正の値では draft・verify・commit の区間を計測し、2 以上では tree verify 内の各段階の詳細計測も有効になります。詳細計測は verify の通常の HIP Graph capture/reuse 経路を通らず、カーネル列を実行して区間を同期・計測します。トークン選択や tree のサイズ決定に値を使う分岐はありません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1857-1863, 4690-4710, 5206-5228`）。

## 値と判定

両読み取り箇所とも `std::getenv` の結果を `std::atoi` に渡します。最初の箇所は未設定でないことに加えて `atoi(...) > 0`、2 番目は未設定なら 0、設定時は `atoi(...) >= 2` で判定します。文字列全体の検証や clamp はありません。したがって空文字、数字で始まらない文字列、`0`、`0anything` はどちらの計測も無効です。`1` や `1tail` は通常計測だけ、`2`・`+2`・` 2tail` は通常計測と詳細計測を有効にします。`true` や `-1` は無効です。大文字小文字比較はありません。`atoi` の整数範囲を超える入力の結果はこのコードで検証・制限されていません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1858-1863, 4692-4695`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| HIP tree step の全体計測 | `tprof=false` | 正の整数。例: `1`, `2tail` | 空文字、`0`, `0anything`, `true`, `-1` |
| tree verify の詳細計測 | `tprof_detail=false` | 整数変換結果が 2 以上。例: `2`, `+2`, ` 2tail` | 空文字、`1`, `1tail`, `0`, `true`, `-1` |

`std::atoi` は文字列先頭の整数部分を変換するため、後続文字列は判定に含まれません。未設定時の既定値は両方とも無効です。読み取り結果を保存する static cache はなく、各 speculative step と各 verify 呼び出しで環境を読み直します。各式では `getenv` を条件判定と変換のためにそれぞれ呼ぶため、同時に環境を書き換えるケースの一貫性はコードで保証していません（同ファイル:1858, 4692）。

## 有効になる条件

- 実行バイナリに Strata の RDNA 向け HIP backend が組み込まれている必要があります。HIP backend は `STRATA_ENABLE_HIP` が有効なときに選ばれ、専用の HIP ソースをビルドします（`engine/CMakeLists.txt:91-104, 146-151`; `engine/src/inkling2/hip/CMakeLists.txt:31-32, 73-83`）。CUDA、gfx906 HIP 互換 backend、Metal、SYCL の実装にはこの変数の読み取り箇所はありません。
- 実行経路が `dspark_spec_step_greedy` に到達する必要があります。同関数は DSpark の存在、slot、context headroom、各種形状・GPU 層条件を満たさない場合は早期に 0 を返します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1796-1803`）。
- CLI の対話実行では、サーバーが単一の active slot で DSpark を使い、生成が greedy かつ penalty なしで、残り生成数と context headroom が十分ある経路に限られます（`engine/src/inkling2/ink_serve.h:762-774`）。条件を満たさない場合は通常経路に進み、この変数による tree 計測は行いません。
- ベンチマーク実行でも `use_dspark && P == 1` で、残り生成数が 2 以上かつ context headroom がある場合に呼び出されます（`engine/src/inkling2/ink_main.cpp:196-205`）。
- 関数内で cooldown、低信頼 probe、GPU/HIP 処理失敗などにより途中 return した場合、tree 全体の `[TREE-PROF]` 行は出ません。正の設定値だけで speculative step の成立が保証されるわけではありません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1877-1883, 2068-2075, 2149-2155`）。

## 実行時の詳細

`dspark_spec_step_greedy` に入った後、tree の scratch 準備等を済ませた位置で `STRATA_HIP_TREE_PROF` を読み、正値なら 4 個の HIP event を作成して draft 開始を記録します。処理が成功して commit まで進むと、draft、verify、commit の終了 event を記録・同期して経過時間を取得し、`[TREE-PROF] pos=... M=... acc=... tot=... | draft=... verify=... commit=...` を stderr に出します（同ファイル:1857-1863, 2007-2014, 2142-2155, 2267-2277）。event 作成・record・計測・destroy の戻り値はこの計測箇所では無視されています。

verify ごとに同じ変数を再読し、変換値が 2 以上なら `tprof_detail` が true になります。この場合、既存の tree verify graph を再利用せず、詳細 event を作成して各段階を計測し、最後に `[TREE-DETAIL] B=... sum=... unemb=... tot=... | ...` を stderr に出します。詳細計測経路は `return true` で抜け、verify graph capture/instantiate/reuse 経路へ戻りません。2 未満では従来の Graph reuse/capture/launch 分岐を使います（同ファイル:4690-4711, 5204-5228）。プロセス起動後の環境変更を固定する cache は見当たらず、次の呼び出しで再評価されます。

## ログと測定値

`STRATA_HIP_TREE_PROF` が正で、処理が tree verify・commit まで成功すると `[TREE-PROF]` 行が stderr に出ます。整数変換結果が 2 以上なら、verify 完了時に `[TREE-DETAIL]` 行も stderr に出ます。どちらもコードが出力する計測値であり、この調査では実行・性能測定をしていません。Strata の資料にこの変数の測定条件や性能値は確認できません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2267-2277, 5206-5217`）。

## 根拠

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1857-1863` — 全体計測の値判定と開始イベント。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1877-1883, 2068-2075, 2149-2155` — 計測ログ前に終了する経路と verify 呼び出し。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2267-2277` — 全体計測と `[TREE-PROF]` の出力。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4690-4711, 5206-5228` — 詳細計測判定、Graph 分岐、`[TREE-DETAIL]` と詳細経路の終了。
- `engine/src/inkling2/ink_serve.h:762-774`, `engine/src/inkling2/ink_main.cpp:196-205` — server / benchmark からの呼び出し条件。
- `engine/CMakeLists.txt:91-104, 146-151`, `engine/src/inkling2/hip/CMakeLists.txt:31-32, 73-83` — HIP backend のビルド条件。
