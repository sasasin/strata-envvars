# `STRATA_DEQUANT_SIDE`

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

CUDA の Prefill における dense-weight GEMM で、重みの FP16 dequantization を compute stream 上で直列に行う代わりに、別の CUDA stream と二つの scratch を使って先行させます。Gemm::native の通常経路では二つの scratch を交互に使い、CUDA event で読み取り完了と dequant 完了を順序付けます。従来と同じ dequant と GEMM を呼び、コードコメントでは積が bitwise 同一とされています。decode 全般の切替ではなく、Prefill の Gemm::native がこの分岐に到達した場合の処理です（engine/src/prefill/gemm.cu:1660-1677; engine/src/prefill/prefill.cpp:3090-3095）。

## 値と判定

CUDA では std::getenv の結果の先頭 1 文字だけを '1' と比較します。文字列全体の parse や数値検証はありません。未設定・空文字は無効、1・10・1anything は有効、0・true・ 1・01 は無効です。大文字小文字や後続文字は先頭文字が '1' かどうか以外に影響しません。HIP では値を読まず常に無効です（engine/src/prefill/gemm.cu:737-744）。

| ビルド・起動条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA | 判定は off。ただし自動設定条件を満たす実行ファイルでは未設定時に起動時 "1" が設定される | 先頭文字が 1（1, 10, 1abc） | 空文字、0, true,  1, 01 など先頭が 1 以外 |
| HIP | 常に off | なし。環境値を参照しない | すべて |
| Metal | Prefill の Metal 分岐は GEMM scratch 設定へ進まない | なし | すべて |

## 有効になる条件

- 値判定が有効で、実行経路が CUDA Prefill であること。HIP は false を返し、Metal の Prefill::init は Metal 専用処理から戻ります（engine/src/prefill/gemm.cu:737-744; engine/src/prefill/prefill.cpp:2443-2454）。
- 初期化または relayout 時に二つ目の GEMM_SCRATCH を確保できること。初期化時に収まらなければ「prefill: GEMM scratch does not fit」で失敗します（engine/src/prefill/prefill.cpp:2717-2723）。
- Gemm::set_dequant_side が nonblocking stream と二組の event を作成できること。失敗時は side scratch を外して false を返し、Prefill は警告を出して処理を続けます（engine/src/prefill/gemm.cu:822-851; engine/src/prefill/prefill.cpp:2722-2723, 2944-2949）。
- Gemm::native の先行する特別経路や scratch 不足時の行分割経路では、通常の二 scratch side-stream 分岐には入りません。CUDA の NVFP4 対応経路などは先に return し、N*K > scratch_elems_ では compute stream 上で行ごとに dequant/GEMM します（engine/src/prefill/gemm.cu:1539-1544, 1646-1677）。
- CUDA CLI は可視 GPU がすべて同一 compute capability のときだけ apply_nv_defaults を呼びます。自動の既定値 "1" は sm_86（STRATA_SM86_PERF=0 で抑止）、sm_89（STRATA_SM89_PERF=0 または STRATA_DEFAULTS=026 で抑止）、sm_120（STRATA_SM120_PERF=0 または STRATA_DEFAULTS=026 で抑止）、sm_121（STRATA_SM121_PERF=0 または STRATA_DEFAULTS=026 で抑止）の表にあります。明示設定があると値が何であっても自動設定はスキップされます。混在 compute capability の複数 GPU では自動設定呼び出し自体をスキップします（engine/src/core/nv_defaults.cpp:41-42, 62, 75-106, 121, 176-179, 208, 222-234; engine/src/program/generate.cpp:4416-4444, 4445-4465）。

## 実行時の詳細

通常の CUDA CLI 起動では GPU 世代別既定値の適用は engine の switch 読み取り前です（engine/src/program/generate.cpp:4416-4444）。gemm_dequant_side() は最初に呼ばれた時点の値を関数内 static const bool に保存するため、同一プロセスで後から環境を変更しても再評価されません（engine/src/prefill/gemm.cu:737-744）。関数は Prefill の必要バイト数計算、初期 scratch 割当、relayout から呼ばれ、on のとき二つ目の GEMM_SCRATCH を数え、取得します（engine/src/prefill/prefill.cpp:2717-2723, 2944-2949, 3718-3729）。

有効時、通常の Gemm::native 経路では side stream が現在の scratch の利用完了 event を待って重みを dequantize し、ready event 後に compute stream が GEMM を実行します。次の呼び出しでは別 scratch に切り替わります。先行 kernel が compute stream 上で進む間に dequant を実行できる構成です。無効時は compute stream 上で dequant の後に GEMM を実行します（engine/src/prefill/gemm.cu:1651-1677）。

## ログと測定値

stream 作成失敗では「prefill gemm: dequant side stream: <CUDA error>」、event 作成失敗では「prefill gemm: dequant side events」が理由になります。Prefill は「prefill: STRATA_DEQUANT_SIDE=1 not taken (<理由>): the dense weights are dequantized in front of their GEMMs」と stderr に出します。scratch の取得不足は初期化エラー、relayout では必要バッファと空き VRAM 等を含むエラー文字列になります（engine/src/prefill/gemm.cu:827-844; engine/src/prefill/prefill.cpp:2721-2723, 2944-2957）。

docs/DETAILS.md:1804 は STRATA_PLE_COMPACT=1、STRATA_PLE_COPY_STREAM=1、STRATA_EMBED_VRAM=1、本変数の4設定をまとめて「prompts +2.2% to +2.6%」と記載しています。4設定を合わせた資料上の値であり、本変数単独の測定値ではありません。同じ表は4設定を bitwise、本変数を CUDA only としています。一方 docs/SETTINGS.md:56 の対応行は「NVIDIA and AMD」としていますが、実装の HIP 分岐は常に off です。この対象範囲表示はコードと一致しません。

## 根拠

- 値の読み取り・backend 分岐・cache: engine/src/prefill/gemm.cu:737-744
- stream/event の作成と失敗理由: engine/src/prefill/gemm.cu:822-851
- 既定値表と明示環境値の優先: engine/src/core/nv_defaults.cpp:41-42, 62, 75-106, 121, 176-179, 208, 222-234
- 起動時の既定値適用と混在 GPU 分岐: engine/src/program/generate.cpp:4416-4444, 4445-4465
- Prefill scratch の確保・relayout・容量計算: engine/src/prefill/prefill.cpp:2717-2723, 2944-2957, 3718-3729
- dense dequant と GEMM の通常・side-stream 経路: engine/src/prefill/gemm.cu:1646-1677
