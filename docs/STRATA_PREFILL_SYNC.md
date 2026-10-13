# `STRATA_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の batched prefill で、処理フェーズの mark ごとに compute queue を待ち、完了したフェーズ名と待ち時間を stderr に出すデバッグ用スイッチです。各 mark で待つため、GPU とホストの非同期実行の重なり方が変わります。CUDA/HIP 側にはこの名前を読む実装が見つからず、通常の推論設定というより SYCL prefill の診断フックです。

## 値と判定

| 環境変数の状態 | `sync` | 動作 |
|---|---:|---|
| 未設定 | false | mark ごとの追加 wait と sync ログを行わない |
| 空文字を含む、何らかの値が設定済み | true | 値の内容にかかわらず mark ごとに wait し、sync ログを出す |

`std::getenv("STRATA_PREFILL_SYNC") != nullptr` だけで判定し、数値変換や文字列比較はしません。したがって `0`、`false`、空文字も有効です。CLI 引数や設定ファイルによる上書きは、この名前の参照箇所にはありません。

## 有効になる条件

- Strata の SYCL prefill 実装 `sycl/src/prefill/prefill.cpp` を通り、`Prefill::run()` から `Prefill::run_impl()` が実行されることが必要です。
- `PfTimer` は `run_impl()` 内で作られます。mark は各 chunk の開始・終了や、実行経路に応じた GDN、QSA、gather、expert copy/GEMM、combine などのフェーズ境界にあります。実行経路によって通る mark は異なります。
- 同じファイル内の参照は `PfTimer::sync` の初期化だけです。CUDA の `src/`、Python サーバー、起動スクリプトからこの名前を読む箇所はありません。
- `STRATA_PREFILL_TIMING` とは独立しています。SYNC だけを設定しても profiling event を作らず、TIMING が有効なときにだけ `PfTimer::on` によるイベント記録・集計が行われます。

## 実行時の詳細

`run_impl()` の `PfTimer pt` 構築時に環境変数を一度読みます。構築後、同じ `run_impl()` 呼び出しの各 chunk/phase mark では保存済みの `sync` 値を使うため、その実行中に環境を変更しても反映されません。次回の `run_impl()` 呼び出しでは再評価されます。layer split の次段も独自の `run_impl()` を実行するため、その段では別の `PfTimer` が作られます。

`sync` が true の場合、`PfTimer::mark()` はまず `s->wait()` を呼び、完了後に次の形式で stderr に出します。

```text
strata prefill sync: mark <連番> phase <フェーズ名> done (waited <ミリ秒> ms)
```

待ち時間は `steady_clock` で測った mark 内の queue wait の経過時間です。連番は `PfTimer` ごとに 1 から増えます。wait に timeout を設けるコードはありません。SYCL wait が `sycl::exception` を投げた場合は `run_impl()` の catch に入り、例外内容とファイル・行を stderr に出して `exit(1)` します。

この wait は各 mark の時点までに queue へ投入された処理を同期させ、hang の切り分け時に最後に完了したフェーズをログで示します。カーネルや値の計算方法を直接切り替える分岐はなく、主な影響は同期位置・非同期 overlap・実行時間と診断ログです。Intel の設計記録は Level Zero v2 adapter での prompt-slot borrowing の hang 調査時に `STRATA_PREFILL_SYNC=1` で各 phase を同期した経緯と、その後 sequence polling による修正を記載しています。現在のコードでも debug switch として残っています。

## 根拠

- `sycl/src/prefill/prefill.cpp:1975-1990`: phase 名、`PfTimer::sync` の `getenv()` による設定有無判定。
- `sycl/src/prefill/prefill.cpp:1992-2009`: mark ごとの queue wait、stderr ログ、および `STRATA_PREFILL_TIMING` 有効時のみ行う event 記録。
- `sycl/src/prefill/prefill.cpp:2101-2108,2167-2170,2219-2229`: `run_impl()` と timer の生成位置、chunk 内の mark 呼び出し。
- `sycl/src/prefill/prefill.cpp:4452-4461,4674-4679,4703-4714`: layer split の次段で別途 `run_impl()` を呼ぶ経路、SYCL 例外処理、`Prefill::run()` の入口。
- `docs/INTEL.md:577-587`: hang の調査で各 phase の同期を使った記録と、その後の修正。
