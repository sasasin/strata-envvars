# `STRATA_IQ4_W4A8`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CUDA の prompt MoE expert 計算で、IQ4_XS / IQ4_NL の積に Strata の pipelined int8 tensor-core kernel を MMQ より先に試します。`1` は両形式、`2` は IQ4_NL の積だけが対象です。対象 kernel が条件を満たさない積は通常の MMQ に渡されます。未設定時は無効です。

この切り替えは `mmq::Context::run()` に入った積にだけ作用します。prompt path が MMQ を選ばない層（たとえば fused expert 経路）には作用しません。CLI と server の両方でも、実際にこの CUDA prompt MMQ 経路を通る場合に限られます。

## 値と判定

CUDA 実装は `std::getenv()` の値を `std::atoi()` に渡し、変換結果がちょうど `1` または `2` の場合だけモードを有効にします。文字列全体の妥当性確認はありません。`atoi` の整数変換に従うため、たとえば `01` や `1tail` は `1`、` 2` や `+2` は `2` として扱われます。空文字、数字で始まらない文字列、`0`、負数、その他の数値は無効（モード `0`）です。整数型で表せない入力の結果は C ライブラリの `atoi` の範囲外であり、実装に追加検査はありません。

| 環境値 | 実装上のモード | 試行する積 |
| --- | ---: | --- |
| 未設定、空文字、または `atoi` 結果が `1` / `2` 以外 | 0 | なし（通常の MMQ） |
| `atoi` 結果が `1` | 1 | IQ4_XS と IQ4_NL |
| `atoi` 結果が `2` | 2 | IQ4_NL のみ。IQ4_XS は通常の MMQ |

変数は `iq4_w4a8_mode()` の関数内 `static const` に初回評価結果を保存します。プロセス中に環境を書き換えても再読込されません。明示的な空文字と未設定は、どちらも `atoi` 結果 `0` です。CLI 引数による上書きはこのコードにはありません。別変数 `STRATA_W4A8_CFG` は kernel の構成選択だけに使われ、モードを有効化しません。

## 有効になる条件

次の条件がそろうと対象 kernel を試します。

- CUDA build で prompt MMQ 機能が組み込まれ、対象の積が `mmq::Context::run()` に届くこと。CMake では `STRATA_NATIVE_EXPERTS` が必要で、CUDA が有効な場合 `strata_mmq` に `moe_mmq.cu` と `moe_iq4_w4a8.cu` を含めます。
- 環境値からモード `1` または `2` が得られること。モード `2` では積の型も IQ4_NL であること。
- 積が IQ4_XS または IQ4_NL であること、expert 数が 1 以上かつ `kGatherGroupMax` 以下、最大行数が正、行数が 128 の倍数であること。重み列数は IQ4_XS なら 256、IQ4_NL なら 128 の倍数でなければなりません。
- NVFP4 activation scale (`p.y_scale`) がなく、現在の CUDA device の compute capability が 8.0–8.8 または 12.0 であること。
- 同じ積について MMQ の launch が K 方向に split しないこと（split では加算順序が異なるため）と、weight pointer が 8-byte、quantized activation pointer が 16-byte に整列していること。

条件を満たさない場合は `run_iq4_w4a8()` が false を返し、呼び出し側は MMQ に続行します。HIP build では同名関数が mode `0` を返す stub に置き換わるため、この変数を読みません。CPU 経路にもこの実装はありません。

## 実行時の詳細

prompt の MMQ path は gate/up と down の各 expert product を `mmq::Context::run()` に渡します。モードが対象 product を許すと `run_iq4_w4a8()` が形式・形状・device・alignment などを検査し、通ればその product の CUDA kernel を launch して MMQ を省略します。decline した場合は同じ `Context::run()` 内で通常の MMQ dispatch に進みます。カーネルの成功後は `ck(cudaGetLastError(), "iq4 w4a8")` で launch error を確認します。

有効値を初めて評価したとき stderr に `strata: prompt experts: the IQ4 W4A8 kernel runs ... (STRATA_IQ4_W4A8=..., config ...; MMQ's bits)` を出し、終了時に `strata: IQ4 W4A8 kernel: ran ...; declined ... (MMQ ran those)` の集計を出します。集計の decline 理由は shape、NVFP4 scales、architecture、MMQ K split、alignment、other type です。モードが無効または未設定なら、この機能固有のログと終了時集計は登録されません。

`STRATA_W4A8_CFG` は別の関数内 static で `atoi` され、未設定時は 0、変換結果が 0–3 の範囲外なら 0 に戻ります。0–3 は kernel 構成を選ぶ値です。カーネルの出力についてソースは MMQ tiling-mode と同じ bit 結果を意図・実装すると説明していますが、この調査では build や GPU test を実行していません。

## 根拠

- `src/prefill/moe_iq4_w4a8.cu:439-451`: `getenv` / `atoi`、モードの static cache、有効時ログ、`atexit` 集計登録。
- `src/prefill/moe_iq4_w4a8.cu:435-437,454-490`: compute capability 条件、対象形式・形状・scale・K split・alignment の拒否条件、kernel launch と集計。
- `src/prefill/moe_iq4_w4a8.cu:383-389`: `STRATA_W4A8_CFG` の読み取りと 0–3 の範囲制限。
- `src/prefill/moe_mmq.cu:473-492`: mode に従う先行試行、成功後の error check、失敗時に MMQ dispatch へ続く流れ。
- `src/prefill/prefill.cpp:4720-4738,5898-5919,5951-5974`: 層ごとの MMQ / fused 選択、および gate/up・down products の `Context::run()` 呼び出し。
- `CMakeLists.txt:2115-2116,2354-2372`: MMQ build の native expert 条件、CUDA build での対象ソース組み込み。
- `include/strata/prefill/moe_iq4_w4a8.hpp:9-18`: kernel の入力契約とモードの説明。
- `docs/DETAILS.md:1082`: 対応 GPU・形式と opt-in についての説明。測定値は pull request 参照としているため、本書では性能値を記載しません。
