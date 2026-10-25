# `STRATA_PF_WMMA`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの内部動作は対象外。

## 役割

CUDA の prompt prefill における一部の MoE expert 計算を、FP16 tensor core を使う WMMA grouped kernel に切り替える opt-in 変数です。主に Volta（compute capability 7.0）で MMQ が `dp4a` を使う場合を対象にしています。通常の MMQ は q8_1 活性値を使いますが、この経路は FP16 活性値を使うため、出力値は既定経路と異なる場合があります。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 要求する |
| その他（例: `0`, `true`, ` 1`） | 無効 |

文字列全体の比較や数値変換はせず、`e[0] == '1'` だけを調べます。判定結果は `pf_wmma()` の関数内 `static const bool` に保存されるため、最初の呼び出し後にプロセス環境を変更しても再評価されません。根拠: `src/prefill/prefill.cpp:1153-1169`。

## 有効になる条件

環境値が要求状態でも、CUDA runtime から可視な GPU が1台以上あり、列挙されたすべての GPU で compute capability major が7以上の場合だけ有効です。GPU 数を取得できない、0台、または属性取得に失敗した場合も無効になります。複数 GPU の場合は1台でも major が7未満なら、このプロセスでは使いません。

HIP のコンパイルでは `pf_wmma()` は環境変数を読まず常に false を返します。Metal にもこの CUDA kernel の実装はなく、同梱の Metal stub は呼び出しを未実行扱いにします。根拠: `src/prefill/prefill.cpp:1153-1169`, `metal/src/engine/stubs_0145.cpp:145`。

## 実行時の詳細

有効な場合でも、prefill の MMQ 経路に入ること、native expert layout であること、fused expert 経路や peer GPU 経路でないこと、layer の形式・tail 配置が WMMA 呼び出しに対応することが必要です。対応する grouped expert 計算では、gate/up の入力行を FP16 に集め、FP16 tensor core kernel で gate/up と down の積を実行します。該当しない layer は通常の MMQ または既存の FP16 経路に残ります。WMMA 専用扱いになった layer で chunk 側が WMMA 経路を取れない場合は、prefill が `an IQ1_M layer in the MMQ grouping needs the WMMA tiles, which this chunk cannot take` エラーで失敗します。

実装上の layer 判定は `mmq_plan()` が行い、実際の分岐は prefill の expert-group 処理から `gemm_iq_f16_grouped()` を呼びます。対象形状には MMQ で扱えない一部形式（コメントでは IQ1_M、IQ4_NL down）も含まれます。根拠: `src/prefill/prefill.cpp:1171-1204,4016-4038,4555-4569`。

## 文書との照合

`docs/NVIDIA_V100.md` はこの変数を opt-in とし、可視 GPU がすべて compute capability 7 以上である条件、および FP16 tensor core prompt expert 経路を説明しています。資料は V100 での prompt speed 数値も報告していますが、その性能値は資料に記載された測定条件に限られ、ここでは再測定していません。同資料も FP16 活性値と既定 MMQ の q8_1 活性値が異なるため、答えが異なることを明記しています。根拠: `docs/NVIDIA_V100.md:28-31,94-101`。

## 根拠

- `src/prefill/prefill.cpp:1153-1169` — 値の読み取り、CUDA/HIP 分岐、GPU 条件、結果のキャッシュ。
- `src/prefill/prefill.cpp:1171-1204` — MMQ plan での layer eligibility と WMMA 専用 layer 判定。
- `src/prefill/prefill.cpp:4016-4038,4555-4569` — chunk / layer の実行条件、FP16 grouped kernel の呼び出しと失敗時のエラー。
- `src/kernels/cuda/iq_kernels.cu:5274-5416` — CUDA WMMA grouped kernel 実装。
- `include/strata/kernels/iq_kernels.hpp:124-128` — kernel の入出力と CUDA 限定の宣言。
- `metal/src/engine/stubs_0145.cpp:145` — Metal 側 stub。
