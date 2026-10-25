# `STRATA_I8_MT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL ESIMD の fused int8 expert kernel で、1スレッドが処理する活性値タイルの高さ `MT`（8行タイル単位）を指定します。対象は prompt の expert gate/up と down 積です。設定しない場合は、expert group の平均タイル数から 2、4、8 を選びます。`MT` は行ブロック分割とカーネルのコンパイル時テンプレート引数に使われます。`sycl/src/prefill/esimd_moe.dp.cpp:4-11,184-197,205-221`。

## 値と判定

実装は `std::getenv()` の結果を `std::atoi()` に渡します。文字列全体の検証や範囲 clamp はありません。未設定なら 0、空文字や整数変換できない文字列も `atoi` の結果が 0 となり、自動選択になります。先頭の空白・符号と数値接頭辞は `atoi` の変換規則に従うため、たとえば `4junk` は 4 として扱われます。

| `atoi` の結果 | 選択・動作 |
|---|---|
| 0 | group ごとに `pick_mt()` で選択。平均タイル数が `<= 2` なら 2、`<= 4` なら 4、それ以外は 8。 |
| 2、4、8 | その `MT` を gate/up と down の両方で使用。 |
| その他の非ゼロ値（例: 1、3、-1） | dispatch に対応ケースがないため、その int8 積は開始されず、呼び出し元がその expert group を FP16 経路で処理。 |

根拠: `sycl/src/prefill/esimd_moe.dp.cpp:747-781,995-1012,1033-1047`。

## 有効になる条件

この変数は int8 kernel の MT 選択だけを制御し、int8 経路そのものを有効化しません。prompt 側で int8 経路が選ばれ、かつ対象 layer が native expert format、gate/up が IQ3_S・IQ3_XXS・IQ2_S、down が IQ4_NL・Q2_0、形状が `n_ff=640`・`n_embd=2560` で、デバイスが必要な ESIMD / s8 DPAS 組み合わせを利用できる場合に限り読み取り結果が使われます。`STRATA_PREFILL_MMQ`（別名 `STRATA_PF_I8`）が int8 経路の選択に関わります。非対応デバイスや適用外の形式・形状では FP16 経路です。`sycl/src/prefill/prefill.cpp:269-287,4227-4236`; `sycl/src/prefill/esimd_moe.dp.cpp:40-60,835-853,978-983,1015-1020`。

## 実行時の詳細

`mt_for()` の関数内 static 変数が `STRATA_I8_MT` を初回評価時に一度だけ読みます。実際の評価は int8 の gate/up または down kernel を呼ぶ経路に入った時です。その後に同一プロセスの環境値を変更しても反映されません。0 の場合に使う自動選択値は `Layout` ごとに計算され、group ごとに変わり得ます。`sycl/src/prefill/esimd_moe.dp.cpp:747-760,995-996,1033-1035`。

`MT` は各 expert の8行タイル数を `MT` ごとの row block に分割し、各カーネルで最大 `MT × 8` 行を処理するために使われます。値 2、4、8 は compile-time dispatch された kernel を起動します。その他の非ゼロ値では `gate_up()` または `down()` が `false` を返します。呼び出し元は int8 products が実行できなかった場合、その group に対して「`the FP16 chain is used`」と stderr に一度ログして FP16 の dequantize・GEMM 経路を使います。`sycl/src/prefill/esimd_moe.dp.cpp:184-197,205-221,774-781,995-1012,1033-1047`; `sycl/src/prefill/prefill.cpp:4290-4317`。

## 根拠と資料との照合

`docs/INTEL_INT8_EXPERTS.md:25-34` は `2|4|8` を強制指定できること、自動選択のタイル閾値、タイル高さの用途を説明しています。ソースではそれ以外の非ゼロ値を拒否する明示的な入力検査はなく、kernel dispatch 失敗から当該 group の FP16 経路へ戻ることを確認しました。ビルドが `STRATA_I8_NO_ESIMD` の場合、該当実装は stub となり `available()` は常に false なので、この環境変数を読む経路に入りません（`sycl/src/prefill/esimd_moe.dp.cpp:40-60`）。
