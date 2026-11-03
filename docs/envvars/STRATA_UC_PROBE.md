# `STRATA_UC_PROBE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL エンジン内で診断用の小規模 GPU カーネル計測を有効にします。モデルの計算設定を選ぶ変数ではなく、engine の in-order queue に計測用バッファを確保し、量子化 + MMVQ、FMA、短い加算カーネル、空 launch を実行して stderr に時間を出すテスト用フックです。`uc_probe()` は engine 起動、モデル準備、serve の準備完了やリクエスト処理など複数地点から呼ばれます（`sycl/src/program/generate.cpp:1800,3083,3095,3691,4455,5244,5784,9143,12475,12643,12764,13313,13724`）。

## 値と判定

helper は `std::getenv("STRATA_UC_PROBE")` の値を数値変換せず、先頭文字だけで判定します。値の全体、大文字小文字、空白、数値としての妥当性は検査しません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外の非空文字列 | 有効（例: `1`, `true`, `false`, `2`, `x`） |

判定結果は `ucprobe::on()` 内の `static const bool` に初回呼び出し時に保存されます。engine 起動後に値を変更しても再評価されません。別の環境変数 `STRATA_UC_POISON` は、この probe の最初の実行後に追加のテストカーネルを行うための独立した設定であり、`STRATA_UC_PROBE` 自体の値判定には使われません（`sycl/include/strata/uc_probe.hpp:26,77-80,151-154`）。

## 有効になる条件

この読み取りと `uc_probe()` 呼び出しは SYCL engine にあります。SYCL の CMake 定義は `sycl/src/program/generate.cpp` を `strata` 実行ファイルに含めます（`sycl/CMakeLists.txt:284-286`）。CUDA/HIP の engine でこの変数を読む実装は、この調査対象 commit の Strata 所有ソースでは見つかりませんでした。

通常の起動では `main()` の引数解析前に `uc_probe("start")` が呼ばれるため、変数が有効なら `--help` を含む通常起動で probe が先に動きます。`--version` / `-V` はその前に戻るため probe を実行しません（`sycl/src/program/generate.cpp:1772-1801`）。probe はモデルや CLI の機能フラグで有効化を制限されず、`uc_probe()` に到達した時点で有効です。serve 経路では準備完了前の `ready`、各リクエスト完了後の `after-request` などでも実行されます（同: `9143-9145,12473-12475`）。

## 実行時の詳細

有効時、各 `uc_probe(tag)` 呼び出しは SYCL queue 用の device buffer 群を作り初期化してから、4 種類のカーネル計測を 3 回行い、各値について最小時間を採用します。計測は各反復前後に queue を wait するため同期的です。さらに profiling event が利用できる場合は FMA と短いカーネルの GPU 時間を計測し、空 kernel launch 200 回から host submit 時間を測ります。最後に登録済み device allocation 量と計測値を `UCPROBE <tag>` の行として stderr に出します。計測用バッファはスコープ終了時に queue を待って解放します（`sycl/include/strata/uc_probe.hpp:28-50,77-150`）。したがって有効化すると、通常処理に入る前や各 probe 地点で待ち時間と GPU 作業が追加されます。

profiling event の取得部分は例外を握りつぶし、その場合 `gpu-stamps` 行の FMA / tiny 値は初期値 `-1` のままです。ほかの probe 処理中に SYCL 例外が発生すると、`main()` の例外 handler が stderr にエラーを書いて終了コード 1 で終了します。device memory allocation 失敗時は「this card does not have the memory for this start」のメッセージを出して終了します（`sycl/include/strata/uc_probe.hpp:112-149`; `sycl/src/program/generate.cpp:13885-13895`）。

有効な probe の最初の実行後だけ、`STRATA_UC_POISON` が設定されていて空でなければ、その値に応じて追加の診断 kernel を実行し、`UCPROBE poisoned with ...` を出して `after-poison` probe を再帰的に呼びます。poison の入力規則やカーネル分岐は `uc_probe.hpp:52-74,151-154` にあり、この文書では `STRATA_UC_PROBE` の外部効果との混同を避けるため概要に留めます。

## 根拠

- 実読み取り、空文字・先頭文字判定、cache: `sycl/include/strata/uc_probe.hpp:26`
- 計測バッファ、同期計測、stderr 出力、probe 後の poison 分岐: `sycl/include/strata/uc_probe.hpp:28-50,77-155`
- 起動時の最初の呼び出しと `--version` の早期 return: `sycl/src/program/generate.cpp:1772-1801`
- serve の準備完了・リクエスト後の呼び出し: `sycl/src/program/generate.cpp:9143-9145,12473-12475`
- SYCL 実行ファイルへの組み込み: `sycl/CMakeLists.txt:284-286`
