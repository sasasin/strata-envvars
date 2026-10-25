# `STRATA_MTP_PROFILE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象の作業ツリーは `main`（`origin/main` と同じ HEAD、調査開始時 clean）。

## 役割

MTP（draft layer）の GPU graph 内に stage 境界の timestamp を記録し、round graph と draft step graph の各区間の平均時間を stderr に出す測定用スイッチです。draft 処理そのものを選択・変更する設定ではありません。ただし有効時は graph に timestamp 用 GPU kernel が加わり、計測値と実行時間に小さな計測オーバーヘッドが入ります。実装コメントも measurement only とし、stamp の追加で合計値が少し高くなると説明しています。

## 値と判定

`MtpProf` のコンストラクタで `std::getenv()` を一度呼び、値が存在し、先頭文字が ASCII の `1` の場合だけ有効になります。文字列全体の parse や数値変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は存在するが先頭文字が `\0`） |
| `1`, `10`, `1anything` | 有効（先頭文字だけを比較） |
| `0`, `true`, ` 1`, その他 `1` 以外で始まる文字列 | 無効 |

環境変数はグローバル静的オブジェクト `g_mp` の構築時に読まれます。したがって通常はプロセス起動時に一度だけ評価され、起動後に環境を書き換えても反映されません。

## 有効になる条件

- MTP draft layer を使う実行であること。MTP を使用しない場合は、グラフの記録・集計・出力経路に入りません。
- `src/core/mtp.cpp` の CUDA/HIP graph 実装が使われること。Metal の `draft()` は `STRATA_GPU_METAL` 分岐で Metal engine に処理を渡して早期 return し、この profiler の集計経路を通りません。SYCL port の `sycl/src/core/mtp.cpp` にもこの変数の読み取り実装はありません。
- 最初の round/step graph capture 前に GPU timestamp buffer の `cudaMalloc` が成功すること。失敗時は profiler を無効にします。この失敗はこの箇所ではログにせず、CUDA error を `cudaGetLastError()` で消費します。
- 少なくとも一つの MTP draft round が実行され、該当 graph の timestamp が記録されること。値が有効でもこの条件がなければ出力はありません。

## 実行時の詳細

round graph の capture 前に 24 slot × 17 graph 分の GPU buffer を確保してゼロ初期化します。実際に使う stage 名は `embed+fc_emb`、`hnorm+fc_hidden+add`、attention/KV、router/experts/shared、combine/write、head、`argmax+prob`、`select` などです。round graph と step graph の各 stage 境界で stream 上に GPU timestamp kernel を追加します。step graph は index が 1〜16 の範囲だけ対象になります。

各 round の GPU 同期後、round とその round で実行した step の stamp buffer を host にコピーします。隣接する有効 stamp の差を区間時間として集計し、round と step を別々に、300 round ごとに stderr に出力します。出力形式は `strata mtp profile (round, ms per graph over N): ... | total ...` または `strata mtp profile (step, ms per graph over N): ... | total ...` で、区間ごとの平均値と合計平均値を ms 単位で示します。ゼロまたは前値より小さい stamp は区間集計から飛ばされます。

測定だけを有効にする想定ですが、実装は GPU buffer の確保、追加 kernel、round ごとの device-to-host copy と集計を行います。よって出力値を profiler 無効時の性能として扱うべきではありません。文書 `docs/DETAILS.md` にはこの環境変数の説明や性能測定値は見つからず、性能上の影響量はソースからは確認できません。

## 根拠

- `src/core/mtp.cpp:748-813` — profiler の用途、24 slot/17 graph、`getenv()` と先頭文字判定、buffer 初期化、timestamp の集計形式。
- `src/core/mtp.cpp:892-1217` — MTP forward の各区間にある stage stamp 呼び出し。
- `src/core/mtp.cpp:1265-1340` — round/step graph capture 時の buffer 初期化と stamp 範囲の設定。
- `src/core/mtp.cpp:1516-1531` — Metal backend は Metal engine に処理を委譲して `draft()` から早期 return。
- `src/core/mtp.cpp:1688-1693` — GPU 同期後の stamp 回収と、300 round ごとの出力。
- `src/kernels/cuda/verify_kernels.cu:1389-1415` — `gpu_stamp` が GPU counter の timestamp を buffer に書き込む実装。HIP/GFX 向けの counter 換算もこの関数内にある。
- `sycl/src/core/mtp.cpp` — 同じ変数名の読み取りは見つからず、SYCL port の別実装ではこの profiler を確認できない。
- `docs/DETAILS.md` — `STRATA_MTP_PROFILE` の説明・測定値を確認できず。
