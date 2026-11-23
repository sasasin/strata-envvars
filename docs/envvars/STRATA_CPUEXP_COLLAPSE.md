# `STRATA_CPUEXP_COLLAPSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4-Flash エンジンの CPU expert 用ホストアリーナに対し、読み込み後に `madvise(..., MADV_COLLAPSE)` を要求するスイッチです。値が有効なら、アリーナを最大 64 MiB ごとの範囲に分け、2 MiB 単位に切り下げてカーネルへ collapse を要求します。これは Strata が呼び出す処理であり、カーネルが実際にページを統合したかは別途ログの `AnonHugePages` と各呼び出しの戻り値で観測します。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1786-1817`

対象ファイルは `STRATA_BUILD_HY4` が有効なときに `strata-hy4` に含まれます。このビルドは CUDA または HIP を必要とします。実行時は HY4 のハイブリッド配置で CPU tier の expert mask が空でない場合に `CpuExperts::init` が呼ばれ、その `load` 中に判定されます。通常の GPU expert 計算や他エンジンを切り替える変数ではありません。`engine/CMakeLists.txt:846-852,884-891`; `engine/src/hy4flash/run/hy4_graph.hip.h:262-265,1552-1565`; `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1700-1704,3059-3061`

## 値と判定

`std::getenv` で取得した文字列の**先頭1文字だけ**を `'1'` と比較します。文字列全体の parse、数値検証、空白除去、大文字小文字変換はありません。未設定または空文字は無効です。`1`, `10`, `1anything` は有効、`0`, `true`, `01`, ` 1`, `1 ` は無効です。既定は collapse 要求なしです。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1805-1816`

| ビルド・OS 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata-hy4` の非 Windows ビルド | collapse 要求なし（ログ上 `off`） | 先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, `01`, ` 1`, `1 `（ログ上 `off`） |
| Windows ビルド | このコード節がコンパイル対象外。環境変数を読み取らず、THP のこのログも出さない | 該当なし | 該当なし |

## 有効になる条件

- `STRATA_BUILD_HY4=ON` でビルドされた `strata-hy4` を実行する必要があります。CMake は HY4 を CUDA または HIP ビルドに限定しています。`engine/CMakeLists.txt:846-852,884-891`
- 実行時にハイブリッド配置で `g.cpu_mask` が空でない必要があります。このときだけ `cpu.init(...)` が呼ばれ、CPU expert アリーナのロード処理に入ります。CPU expert が選ばれない場合は環境変数を読む地点に到達しません。`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`
- collapse 節は `_WIN32` 以外でコンパイルされます。実装コメントは Linux の `MADV_COLLAPSE`（Linux 6.1 以降）を説明していますが、コードの OS ガード自体は「非 Windows」です。`MADV_COLLAPSE` がヘッダーにない場合も値 `25` を定義して呼び出します。したがってカーネルが要求を受理する保証はなく、失敗時はログに計上されます。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1786-1812`
- CLI 引数や別の環境変数による優先・上書きはこの判定箇所にありません。HY4 呼び出し元で `HY4_CPU_THREADS` がスレッド数を決めますが、collapse の条件には使われません。`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1565`; `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1805-1816`

## 実行時の詳細

`CpuExperts::Impl::load` はアリーナを確保し、expert body を読み込んで resident expert の参照を設定した後、THP 計測・collapse 節に入ります。アリーナは POSIX 側で `mmap` され、2 MiB 境界に整列され、確保時に `MADV_HUGEPAGE` も best-effort で要求されています。したがってこの変数はその初期要求を切り替えるものではなく、ロード後に即時 collapse を追加要求します。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1617-1628,1700-1730,1774-1817`

環境値は `load` のこの地点で1回取得され、関数内キャッシュやリクエストごとの再読込はありません。アリーナのロード時にそのプロセス環境に設定されている必要があり、同一プロセスで後から変更しても、このロードの判定や処理には反映されません。別の `CpuExperts::load` が呼ばれれば、その呼び出しでは再取得します。子プロセスへの転送・上書き処理はこの実装にありません。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1802-1816,3059-3061`

値が有効なとき、`arena_size` を最大 64 MiB のチャンクに分け、各チャンク長を 2 MiB の倍数に切り下げます。0 長の範囲は飛ばし、各範囲で `madvise(arena + off, len, MADV_COLLAPSE)` を実行します。戻り値 0 の範囲長を `okb`、失敗した範囲長を `badb` に加算します。ここでの失敗は `load` の失敗にはせず、処理を続けます。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1805-1813`

## ログと測定値

非 Windows のこの節に到達すると、値が unset または無効でも stderr に次の形式の行を出します（数値部分は実行時の計測値です）。

```text
[cpuexp] THP: AnonHugePages %.2f GB -> %.2f GB of %.2f GB arena (collapse %s: %zu MiB ok, %zu MiB failed, %.1f s)
```

`collapse` は有効判定時 `on`、それ以外は `off` です。前後の `AnonHugePages` は `/proc/self/smaps_rollup` の `AnonHugePages:` 行を読みます。ファイルを開けない、または該当行を読めない場合は初期値 `-1` のままなので、ログの値は `-1` 由来の値になり得ます。有効値でも、すべての範囲が失敗すれば `0 MiB ok` と失敗量が表示されます。collapse の失敗自体について個別の errno や警告は出しません。ソース資料に測定条件付きの性能値は見つからず、この文書では性能効果を断定しません。`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1792-1817`

## 根拠

- 候補名の実行時参照は `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1805-1816` の `getenv` と判定・ログです。リポジトリ全体の検索では、ほかに `terminal/data/settings-register.json:4264` のレジストリ項目があり、動的 helper に渡す参照はありません。
- ビルド条件と HY4 実行経路: `engine/CMakeLists.txt:846-852,884-891`; `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`。
- アリーナ確保とロード順: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1617-1628,1700-1730,1774-1817`。
