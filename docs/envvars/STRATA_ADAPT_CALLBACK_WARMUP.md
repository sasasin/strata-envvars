# `STRATA_ADAPT_CALLBACK_WARMUP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの内部動作は対象外。

## 役割

Linux の `strata generate` 経路で、CPU の `ExpertPool` を作る前に GPU host callback を一度だけ no-op で実行・同期します。後続の CPU pool 初期化より前に callback の実行経路を通しておくためのウォームアップです。既存の swap 選択、検証 window ごとの callback、residency 更新をこの環境変数が直接変更する処理はありません。

## 値と判定

実装は `std::getenv()` の有無と値の先頭文字だけを調べます。文字列全体の parse、数値変換、大文字小文字変換はしません。

| 値 | ウォームアップ |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（設定ありだが `e[0] == '\0'`） |
| 先頭文字が `0` | 無効。例: `0`, `0anything` |
| それ以外の文字列 | 有効。例: `1`, `false`, ` true`, `anything` |

値の判定は pool 初期化直前の `generate` 経路で行われ、結果を保存する `static` キャッシュはありません。したがって同一プロセス内でこの経路に再度入れば、その時点の環境値を読み直します。CLI オプションや設定ファイルによる上書きはこの分岐にはありません。

根拠: `src/program/generate.cpp:5853-5867`。

## 有効になる条件

- `#if defined(__linux__)` の範囲内でのみコンパイルされるため、非 Linux ではこの読み取りも処理もありません。
- `strata generate` の当該初期化経路を通る必要があります。
- Linux 上で GPU runtime API を利用するビルドが対象です。環境変数が有効でも、その API 呼び出し自体の成否は別に判定されます。
- この処理は `ExpertPool` を `pin=true` で構築する直前にあります。pool の worker/host thread の配置や pinning 設定を変えるものではありません。

## 実行時の詳細

値が有効なら、Strata は null/default stream に no-op callback を enqueue し、その stream を同期します。両 API 呼び出しが成功した場合、stderr に `strata generate: GPU host-callback thread started before host-core pinning` を出します。どちらかが失敗した場合は `cudaGetLastError()` を呼び、`strata generate: could not warm up the GPU host-callback thread (continuing)` と出して続行します。失敗しても generate はこの箇所で終了せず、その後の pool 構築へ進みます。

直後に `ExpertPool(..., pin=true, ...)` を構築します。pool 実装は Linux で pool 配置を決める際に呼び出し元 thread の許可 CPU を読み、スレッド affinity を設定する helper を持ちます。ソースコメントでは、host thread を pin した後に callback 実行 thread が初めて作られると、同じ CPU mask を引き継いで host の spin-wait と競合しうることを理由として挙げています。この環境変数が制御するのは、その前段にある no-op callback の warm-up と同期、および成否ログです。

根拠: `src/program/generate.cpp:5854-5873`, `src/kernels/cpu/pool.cpp:580-590,644-665,743-748`, `src/kernels/cpu/pool_affinity_linux.hpp:51-65`。

## 文書・測定との照合

`docs/DETAILS.md:2023-2028` も Linux で既定有効、`=0` で無効と記し、swap selection / per-layer callback / residency update は変わらないとしています。同資料は RTX 5090 と Ryzen 9 9950X の paired 4K three-prompt test について平均 142.82 → 207.75 tok/s と記載しています。これは資料に記された単一構成の測定結果であり、他の GPU・driver での性能を示すものではありません。コード上では測定や性能保証は行いません。
