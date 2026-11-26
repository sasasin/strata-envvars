# `--ple-io`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数。`strata` / `strata.exe`） |
| オプション | `--ple-io` |
| 別名 | なし |
| 値 | `direct`、`mmap`、`ram` のいずれか |

## 役割

PLE（n-gram）テーブルの読み出し方を選ぶ。`direct` はテーブルをメモリマップせず行を直接読み、`mmap` はファイルをマップしてOSのファイルキャッシュを使い、`ram` はマップしたテーブルを起動時にページインしてロックを試みる。`--ple-gguf` でPLEテーブルを指定した実行経路に適用される。エンジンのusageにも3値と既定値が記載されている（`engine/src/program/generate.cpp:1218-1224`）。

## 使い方

```sh
# 指定したPLEテーブルをOSのファイルキャッシュ経由で読む
strata generate --pack /path/to/pack --tokens "1,2,3" --ple-gguf /path/to/ple.gguf --ple-io mmap

# 対応環境でテーブルをページインし、RAMロックを試みる
strata generate --pack /path/to/pack --tokens "1,2,3" --ple-gguf /path/to/ple.gguf --ple-io ram
```

## 値と既定値

- 省略時は `direct`。parser の初期値は `"direct"`（`engine/src/program/generate.cpp:817-819`）。
- `direct`、`mmap`、`ram` 以外は受理されず、空文字列も同じ検証により不正値となる。値を省略すると `--ple-io needs a value` を stderr に出して終了コード `2`（`engine/src/program/generate.cpp:3842-3847, 5009-5012`）。
- 同じオプションを複数回指定した場合、parser は各出現で値を代入するため最後の値が残る。いずれかを明示した事実も記録され、自動選択より明示指定が優先される（`engine/src/program/generate.cpp:3901`）。
- オプションの値は常に検証されるが、読み出し方式の設定は `--ple-gguf` が空でない場合にテーブルを開く処理で使用される（`engine/src/program/generate.cpp:6269-6276`）。

## 実行時の動作

`direct` は非バッファの直接読み込み経路を選び、`mmap` と `ram` はメモリマップ経路を選ぶ。`ram` の場合のみロックを要求する。直接読み込み経路では、reader にテーブルのオフセットと行数を渡し、マッピングを保持しない（`engine/src/program/generate.cpp:6270-6276`; `engine/src/kernels/ngram.cpp:448-466`）。

CUDA/HIP 側の `engine/src/program/generate.cpp` では、値を明示せず `direct` のままの場合、使用可能メモリ、PLEテーブルと専門家アリーナのサイズ、8 GiBの余裕を基に `ram` への自動切替を判定する。未知のメモリ情報・テーブルサイズ・アリーナサイズは適格とせず、`STRATA_DEFAULTS=026` の既定方針でも自動選択しない。Appleでは `STRATA_PLE_AUTO_RAM=1` がなければこの自動方針を無効にする。`STRATA_PLE_AUTO_RAM` が設定されている場合は `0` が無効、それ以外の整数値は有効として判定される（`engine/include/strata/core/ple_residency.hpp:25-37`; `engine/src/program/generate.cpp:6303-6325`）。条件を満たしてマップ・ロックを再試行できると direct から `ram` に切り替えた旨を stderr に出す。再オープンに失敗した場合は direct に戻し、それも失敗なら終了コード `1` で失敗する（`engine/src/program/generate.cpp:6324-6346`）。明示した `--ple-io` はこの自動RAM選択を抑止する。SYCL側の同じ起動処理にはこの自動RAM選択がなく、`direct` として開始する（`engine/sycl/src/program/generate.cpp:3350-3372`）。

direct 読み込みの起動時プローブは `STRATA_PLE_PROBE` が未設定の場合に走る。測定値が 15,000 rows/s 未満かつ0より大きいと遅い旨を警告する。既定では直接方式を維持する。未指定のまま `STRATA_PLE_AUTO_MMAP` に非0値を設定している場合だけ `mmap` に切り替える。明示した `--ple-io direct` はこの自動切替を抑止し、遅い場合も警告にとどまる（`engine/src/program/generate.cpp:6350-6383`; SYCL側も同じ判定: `engine/sycl/src/program/generate.cpp:3373-3407`）。

## 適用条件と副作用

- `mmap` はテーブルを実行中マップしてファイルキャッシュを利用する。Windowsで、PLEテーブルと専門家データが同じGGUFにあり、専門家側のマップを閉じた場合には、PLE側のマップが残るため専門家読み込みが直列化されることを通知する（`engine/src/program/generate.cpp:12266-12271`）。
- `ram` は起動時に全テーブルのページを触り、ページロックを試す。テーブルサイズが搭載RAMの半分を超えるWindows環境では警告する。Windowsのロック失敗は部分ロックを解除してページを触るだけにし、POSIXの `mlock` 失敗もページを常駐させたまま警告して続行する。したがってロック失敗自体は起動失敗ではない（`engine/src/kernels/ngram.cpp:467-491, 497-545`）。
- SYCLビルドでは Windows 上の `--ple-io ram` は stderr に利用不可の案内を出して終了コード `2` となり、`mmap` を案内する。CUDA/HIP側の処理とは異なる（`engine/sycl/src/program/generate.cpp:2517-2526`）。
- 非Windowsで `direct` のテーブルが回転ディスク上にあると検出された場合は、プロンプト処理が長時間停止し得る旨を警告する。方式を強制変更はしない（`engine/src/program/generate.cpp:6385-6395`; SYCL側: `engine/sycl/src/program/generate.cpp:3408-3418`）。
- `mmap` / `ram` はテーブルのマッピングを保持する一方、`direct` では保持しない。通常のGGUF読込・テーブル形式検証に失敗すると stderr に理由を出し、エンジン処理は終了コード `1` で失敗する（`engine/src/kernels/ngram.cpp:364-446`; 呼び出し側: `engine/src/program/generate.cpp:6288-6291`）。

## 出力とエラー

- 値が不正: `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` を stderr に出し、終了コード `2`（`engine/src/program/generate.cpp:5009-5012`）。
- 値の欠落: `--ple-io needs a value` を stderr に出し、終了コード `2`（`engine/src/program/generate.cpp:3844-3847`）。
- 明示的な `ram` がロックできない場合: `strata: PLE table ... lock failed` 等を stderr に出して続行する。出力はOSとロック失敗理由で異なる（`engine/src/kernels/ngram.cpp:467-491, 516-542`）。
- direct の遅い測定、回転ディスク、または自動RAM選択は警告・案内を stderr に出す。通常はそれ自体で異常終了せず、自動切替は上記の条件に限られる（`engine/src/program/generate.cpp:6333-6345, 6352-6395`）。

## 根拠

- ツール・scope: `docs/cli/README.md:1036-1042` は `strata-engine` のトップレベル「エンジン引数」を `strata-engine/root/` に配置している。
- 値の初期値・usage: `engine/src/program/generate.cpp:817-819, 1218-1224`。
- 値取得・検証: `engine/src/program/generate.cpp:3842-3847, 3901, 5009-5012`。SYCL parser: `engine/sycl/src/program/generate.cpp:1882-1887, 1940, 2517-2526`。
- 読み方の指定・メモリ方針・probe: `engine/src/program/generate.cpp:6269-6289, 6292-6383`。SYCL側の読み方・probe: `engine/sycl/src/program/generate.cpp:3350-3407`。
- テーブルのマッピング、直接reader、ページロックと失敗時の継続: `engine/src/kernels/ngram.cpp:364-466, 467-545`。
- ディスク警告とWindowsでの同一GGUFへの影響: `engine/src/program/generate.cpp:6385-6395, 12266-12271`。
