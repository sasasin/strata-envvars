# `STRATA_GDN_CHUNK_PROF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Volta (compute capability 7.0) 向け GDN chunk recurrence の CUDA 処理時間を、CUDA event で測って標準出力へ出す開発・診断用フックです。GDN の chunk recurrence を選ぶ設定ではなく、選択済みの chunk 処理に計測とログを追加します。

## 値と判定

この変数は値を parse せず、`std::getenv("STRATA_GDN_CHUNK_PROF") != nullptr` で設定有無だけを見ます。したがって未設定なら無効、空文字を含め何らかの値が設定されていれば有効です。`1` 以外や `0` も有効です。

判定結果は `gdn_chunk_recurrence()` 内の `static const bool` に保存されます。最初に同関数へ到達したときに一度だけ判定するため、その後の環境変更はプロセス内で反映されません。ただし関数の先頭で `T <= 0` または64未満の `T` は return するので、その呼び出しだけでは環境変数の判定は行われません。

## 有効になる条件

- `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA build に chunk 実装が含まれていること。HIP build とこの macro のない build では `gdn_chunk_available()` は false です。
- 対象 device の compute capability が 7.0 であること。
- `gdn_recurrence()` が serial 経路でなく、`T > 0` で、`STRATA_GDN_CHUNK` が parse 後に0以外となり、少なくとも64 token の chunk prefix があること。`STRATA_GDN_CHUNK` が unset の場合は通常の経路となります。

したがって `STRATA_GDN_CHUNK_PROF` だけを設定しても chunk recurrence は起動しません。適用条件の確認に使われる `STRATA_GDN_CHUNK` は呼び出しごとに読み取られ、空文字は -1、その他は `atoi()` で変換されます。chunk recurrence の dispatch と、この診断変数の詳細は別の挙動です。

## 実行時の詳細

`gdn_chunk_recurrence()` は `T` を64の倍数へ切り下げ、最大32 chunk ずつ処理します。計測が有効だと CUDA event を2つ作成し、各 segment で cumsum、次の kernel、必要な場合は forward kernel の区間を記録します。各区間の終わりに `cudaEventSynchronize()` を行うため、計測時には通常の非同期実行へ同期点が加わります。

標準出力の書式は `gdn_chunk prof T=<T>: cumsum <ms>ms stage2 <ms>ms stage3 <ms>ms` です。実装コメントは「whole call」の時間としていますが、`ms` は各 segment ごとに同じ要素へ代入され、合計されません。そのため出力される数値は最後の segment の計測値です。また、Volta の WMMA 経路では stage2 が WMMA kernel、stage3 は forward kernel を起動しない区間です。FMA 経路では stage2 が KKT kernel、stage3 が forward kernel です。ログの `T` は端数 token を含む関数引数で、chunk kernel が処理するのはその64の倍数部分です。

計測終了後に両 event を破棄します。計測値は診断ログであり、出力が chunk 処理の速度を示すものとして計測区間外の処理を含むとは限りません。

## 根拠

- `src/prefill/gdn_chunk.cu:523-529` — build macro、HIP、compute capability による利用可能性。
- `src/prefill/gdn_chunk.cu:531-545` — `T` の早期 return と chunk 関数内の設定読み取り位置。
- `src/prefill/gdn_chunk.cu:579-584` — WMMA/FMA の選択、segment 数、診断変数の存在判定。
- `src/prefill/gdn_chunk.cu:587-632` — event 計測、同期、ログ書式、event 破棄。`ms` が segment ごとに上書きされることもこの範囲から確認。
- `src/prefill/kernels.cu:2666-2692` — `STRATA_GDN_CHUNK` による dispatch、chunk prefix と短い tail の処理。
- `include/strata/prefill/gdn_chunk.hpp:60-76` — API の対象と64 token chunk の契約。
