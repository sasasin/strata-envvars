# `DS4_SERIAL_PREFETCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

macOS の DSV41 engine が IQ 形式 expert を CPU lane で処理するとき、複数 expert の行列を先に prefetch する経路を逐次実行にします。未設定なら、通常の prefetch 経路は NUMA node 用の pool に行列ごとの処理を渡します。この環境変数は値を解釈せず、設定の有無だけでその並列経路を選ばないようにします。

## 値と判定

| 状態 | 判定と結果 |
|---|---|
| 未設定 | 他の条件も満たせば複数行列の prefetch を `run_nodes()` 経由で node pool に渡す |
| 空文字を含む設定済みの値 | `getenv(...) == nullptr` が偽になるため、並列経路を選ばない |
| 任意の非空値（`0`, `1`, `false` など） | 値の parse・比較はせず、設定済みとして並列経路を選ばない |

対象変数の値は数値変換されず、無効値、大小文字、境界値の概念はありません。設定済みの場合に `pf_all` が真なら `os::prefetch(want)` を呼び、範囲を呼び出し元スレッドから順に処理します。

## 有効になる条件

環境変数が実際に分岐を変えるのは、`__APPLE__` のコードで、`cpu_experts_iq()` に入り、かつ以下を満たすときです。

- `pf_all` が真。これは `DS4_IQ_PF_COLD` が未設定、または設定値の `atoi()` 結果が 0 の場合です。
- `DS4_CPU_LOG` による cache census 経路に入らない。
- `want.size() > 1`。`want` は CPU lane の対象 expert ごとに3行列を加えますが、`store` または RAM copy にある expert は追加しません。

`DS4_CPU_LOG` が有効で `pf_all` も真の場合は、先行する census 分岐が各行列に対して `os::prefetch({w})` を直接呼ぶため、`DS4_SERIAL_PREFETCH` の判定箇所を通りません。`want.size() <= 1` の場合も通常の `os::prefetch(want)` となり、変数による差はありません。`pf_all` が偽なら `os::prefetch_cold(want)` を使い、この環境変数は判定に関与しません。

この処理は `#if defined(__APPLE__)` 内にあります。Apple 以外では `DS4_SERIAL_PREFETCH` を読むコードがコンパイル対象にならず、環境変数を設定してもこの処理には影響しません。`cpu_experts_iq()` は `cpu_experts_mx()` から、層の expert が MXFP4 でない場合に呼ばれます。MoE 層で router が選んだ expert のうち CPU lane 側にある expert があり、CPU 処理を skip していない実行経路が対象です。

## 実行時の詳細

`DS4_SERIAL_PREFETCH` の `getenv()` は `cpu_experts_iq()` の prefetch 分岐ごとに呼ばれ、結果は static cache されません。したがって、分岐評価時のプロセス環境の値が使われます。CLI 引数による上書き、対象変数の値を設定する子プロセス処理、警告や失敗処理はこの参照箇所にはありません。

通常の Apple 経路では、`pf_all && want.size() > 1` のとき、変数が未設定なら各 range の `os::prefetch()` を `run_nodes()` に渡します。`run_nodes()` は `NH` 個の pool に仕事を開始させ、pool 0 が help した後、各 pool を wait します。設定済みならこの処理を飛ばし、`pf_all` 分岐の `os::prefetch(want)` に進みます。共通 helper は range を順に走査し、Apple では各 range に `madvise(..., MADV_WILLNEED)` を呼びます。これは prefetch の順序・発行方法を変えるもので、expert の選択や CPU expert 計算の数値処理を変える分岐ではありません。

`DS4_CPU_LOG` が有効な census 経路では、prefetch 前に `mincore()` で各行列の cache 状態を調べ、終了時に cold/warm の件数と prefetch 時間を stderr に出します。通常の `DS4_SERIAL_PREFETCH` 分岐自体には専用ログ、警告、終了コードやエラー処理はありません。`os::prefetch()` の `madvise()` 戻り値もこの helper では検査しません。

## 根拠

- `src/dsv41/ds4_model.cu:6455-6456`: MXFP4 でない CPU lane expert の処理を `cpu_experts_iq()` へ渡す。
- `src/dsv41/ds4_model.cu:6648-6680`: prefetch range の構築、`DS4_IQ_PF_COLD` の既定判定、Apple 限定の census / 並列 / 通常経路と `DS4_SERIAL_PREFETCH` の存在判定。
- `src/dsv41/ds4_model.cu:10469-10523,10555-10563`: router の選択結果を GPU resident と CPU lane に分け、CPU lane entries があれば CPU expert 処理を呼ぶ。
- `src/dsv41/ds4_model.cu:6442-6446`: `run_nodes()` が node pools に仕事を開始し、完了を待つ。
- `src/dsv41/ds4_os.hpp:347-365`: `os::prefetch()` が range を順に処理し、非 Windows では各範囲に `madvise(MADV_WILLNEED)` を呼ぶ。
- `docs/envvars/000_envvers.md:279`: 候補一覧に名前があることのみ確認。実際に読む実装は上記の Apple 限定分岐。
