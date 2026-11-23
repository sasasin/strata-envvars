# `STRATA_HC_Q8_BF16TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の Q8_0 hyper-connection read で、BF16 Tensor Core を使う down/up カーネル経路を選びます。`launch_q8_t` はこの値が 1 以上なら通常の up 計算に `gr_up_q8_bf16tc_kernel` を使い、2 以上なら down 側にも `gr_down_q8_bf16tc_kernel` を使います。1 の場合の down は `gr_down_q8_fast_kernel<T, 4, true>` です（`engine/src/kernels/cuda/fused_gr.cu:3943-3955,3974-3987`）。

この判定に到達する前に `STRATA_HC_Q8_TC` の経路が成立すると、INT8 Tensor Core の down/up を起動して return するため、本変数は使われません。同変数が未設定ならその先行経路は CUDA sm_80 以上で既定有効です。BF16TC 経路を選ぶには通常 `STRATA_HC_Q8_TC=0` で先行経路を止めます（同 `:3902-3923,3958-3988`）。

## 値と判定

CUDA で Q8 read を起動した際、`hc_q8_bf16tc_mode()` 内の `static const int env` が初回に `std::getenv` し、空でなければ `std::atoi` します。その後の呼び出しでは値を再取得しません。未設定・空文字は内部値 `-1` になり、sm_80 以上で既定の mode 1 に解決します。`atoi` のため文字列全体の検証はなく、数値の先頭部分だけが変換されます（同 `:3943-3955`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| CUDA build、CUDA device の compute capability major が 8 以上 | 既定 mode 1 | 正の変換値。`1` は BF16TC up、`2` 以上は BF16TC down と up | 変換結果 `0` は off。例: `0`, `0anything`, `true`, `abc` |
| CUDA build、device 判定失敗または major が 8 未満 | mode 0 | なし | すべて無効（値に関係なく関数が 0 を返す） |
| HIP build (`__HIPCC__`) | mode 0 | なし | 値を読み取らず常に無効 |

空文字は unset と同じ既定扱いです。負の変換値（例 `-1`）も `env > 0` を満たさず既定 mode 1 になります。`atoi` は先頭の空白や符号を許し、変換可能な先頭部分を読むため、例えば ` 2tail` は mode 2、`1tail` は mode 1 です。大文字小文字の比較や文字列全体の妥当性検査はありません。正の値は 1 と 2 の二段階を超えても上限 clamp されませんが、実際の分岐はいずれも `>= 1` / `>= 2` です（同 `:3947-3955,3977-3987`）。

## 有効になる条件

- `fused_gr_read_multi_slice` が `q8_down` と `q8_up` の両方を受け取ること。この条件で `launch_q8` を呼び、そこで初めて本変数の mode が評価されます。Q8 の重みが渡されない read では本変数は読まれません（`engine/src/kernels/cuda/fused_gr.cu:4258-4289`）。
- HIP build ではなく CUDA build であること。HIP の `hc_q8_bf16tc_mode()` は値を読む前に 0 を返します（同 `:3943-3951`）。
- CUDA device の compute capability major が 8 以上であること。device 判定に失敗した場合も無効です（同 `:3926-3941,3952-3955`）。
- 先行する `STRATA_HC_Q8_TC` 経路が選ばれないこと。sm_80 以上では同変数が unset / 空 / 非数値 / 負値なら mode 1 に解決され、かつ launch 形状条件を満たすため、BF16TC の判定まで進みません。明示的な `STRATA_HC_Q8_TC=0` が通常の無効化方法です（同 `:3902-3923,3962-3973`）。
- launch 形状が `(LR % 32 == 0) && ((Q8_KC / 32) % 2 == 0) && ((LR / 32) % 2 == 0)` を満たすこと。満たさない場合は BF16TC branch を通らず後続の通常 Q8 経路に進みます（同 `:3977-3988`）。
- CLI による上書きはこのコードにはありません。別環境変数 `STRATA_HC_Q8` やモデルの pack / architecture default は Q8_0 の重みが準備されるかに関係しますが、本変数の mode 判定を上書きしません。Q8 重みの準備と `FusedGrArgs` への受け渡しは `engine/src/core/native_dense.cpp:47-98,530-545`、引数への設定は `engine/src/core/verify.cpp:1796-1808` にあります。

## 実行時の詳細

Q8 read の launch ごとに `launch_q8_t<T>` がまず `hc_q8_tc_mode()` を評価します。INT8 TC mode が 1 以上で形状条件を満たすと、その down/up kernels を起動して関数を抜け、本変数を評価しません。先行経路を通らない場合、本変数の mode を見て BF16TC kernels を選びます。mode 1 は fast down + BF16TC up、mode 2 以上は BF16TC down + BF16TC up です。どちらの down/up の組も GPU stream 上へ enqueue されます（`engine/src/kernels/cuda/fused_gr.cu:3958-3988`）。

本変数自体は最初の `hc_q8_bf16tc_mode()` 呼び出し時に一度だけ読み取られ、プロセス内でキャッシュされます。実行中に環境を変更しても再評価されません。sm_80 条件の device 属性判定も `hc_q8_sm80_fast()` が device ごとに cache します（同 `:3926-3955`）。

## ログと測定値

この変数の値や mode を示す専用ログはありません。Q8 kernel launch 後に CUDA launch error があれば `fused_gr_read_multi q8: %s` を stderr に出し、`exit(1)` します。環境変数が無効値の場合の警告はありません（`engine/src/kernels/cuda/fused_gr.cu:4284-4291`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:3943-3955` — 値の読み取り、変換、既定値、HIP / compute capability 条件。
- `engine/src/kernels/cuda/fused_gr.cu:3958-3988` — `STRATA_HC_Q8_TC` の優先経路、形状条件、カーネル選択。
- `engine/src/kernels/cuda/fused_gr.cu:4258-4291` — Q8 重みを使うときの呼び出しとエラー出力。
- `engine/src/core/native_dense.cpp:47-98,530-545`、`engine/src/core/verify.cpp:1796-1808` — 関連する Q8 重みの用意とカーネル引数への設定。
