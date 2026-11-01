# `DS4_READ_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows で Strata の DeepSeek-V4.1 エンジンがファイルを unbuffered に読むとき、十分大きい1回の read を複数の overlapped read に分けて同時発行する数を指定します。通常の読み取り API や GPU の計算方法を切り替える変数ではなく、`pread_direct()` の Windows 分岐にだけ作用します。

この機能は別実行ファイル `strata-dsv41` に含まれ、CMake の `STRATA_BUILD_DSV41` は既定で OFF です（`CMakeLists.txt:906-910,918-920`）。

## 値と判定

値は `std::atoi()` で整数に変換し、その結果を 1〜16 に clamp します。文字列全体の検証はしません。未設定なら既定値は 1 です。

| 環境変数の値 | `split` | 結果 |
|---|---:|---|
| 未設定 | 1 | 分割しない |
| 空文字 | 1 | `atoi` が 0 を返し、下限の 1 に clamp |
| `0`、負数、整数として読めない文字列 | 1 | 0 または負数を下限の 1 に clamp |
| 1〜16 の整数 | その整数 | 条件を満たす read をその数を目安に分割 |
| 16 より大きい整数 | 16 | 上限の 16 に clamp |

`atoi` のため、先頭の空白や符号を含む整数は変換され、数字の後ろに続く文字は検査されません（例: `4extra` は 4）。数値として読めない先頭なら 0 となり、1 に clamp されます。範囲外の整数を `atoi` に渡した場合の変換結果は C/C++ の仕様上保証されません。

根拠: `src/dsv41/ds4_os.hpp:125-128`。

## 有効になる条件

次の条件をすべて満たす場合に分割読み込みへ進みます。

- `_WIN32` でコンパイルされた実行ファイルである。Linux/macOS 側の `pread_direct()` は `#else` 分岐で、`DS4_READ_SPLIT` を読まず、通常の `pread` を行います（`src/dsv41/ds4_os.hpp:113-114,179-190`）。
- `split` が 1 より大きい。
- `pread_direct()` が呼ばれ、アラインメントを含む読み取り長 `need` が 2 MiB 以上かつ 1 GiB 未満である。境界未満または 1 GiB 以上では、同関数の逐次読み込み経路を使います（`src/dsv41/ds4_os.hpp:123-129,155-178`）。
- 読み取り対象に unbuffered handle があり、呼び出し側が直接読み込みを選択している。Windows では `open_direct()` がその handle を開きますが、`DS4_WIN_DIRECT` が設定され `atoi(value) == 0` なら開かず、直接読み込みは使われません（`src/dsv41/ds4_os.hpp:82-95`）。

DeepSeek-V4.1 の GGUF 読み込みでは、モデルの file handle を `dfds` に保持し（`src/dsv41/ds4_model.cu:386-404`）、専門家の read job が `pread_direct()` を呼びます。対象ページが map 上で resident ならその直接 read は避けられます（`src/dsv41/ds4_model.cu:4017,4060,8975`; `src/dsv41/ds4_pool.hpp:220-241`）。また、モデル file の view を外した後の `Pack::read_at()` も `direct_reads` が有効な場合に直接 read を試します（`src/dsv41/ds4_model.cu:455-470,481-497,3186-3200`）。

## 実行時の詳細

`split` は `pread_direct()` 内の function-local `static const int` です。プロセスでこの関数が最初に実行された時点の環境から一度だけ決まり、その後に環境を変更しても再評価されません（`src/dsv41/ds4_os.hpp:113,125-128`）。CLI 引数や別の Strata 設定から値を上書きする処理はありません。`DS4_WIN_DIRECT=0` は直接読み込み handle を無効にするため、この変数の分割処理にも到達しません。

分割経路では `need` を `split` に応じて分け、各区間について `ReadFile()` を発行してから `GetOverlappedResult()` で完了を待ちます。各区間長は 4096 byte 境界に合わせられます。分割 read の発行または完了が失敗した場合、`pread_direct()` は失敗を返します。呼び出し側は `ds4_pool.hpp` で buffered `pread_par()` に fallback し、`Pack::read_at()` も buffered handle または通常 handle を試します。したがってこの値が直接変えるのは unbuffered read の発行方法です（`src/dsv41/ds4_os.hpp:129-153`; `src/dsv41/ds4_pool.hpp:220-241`; `src/dsv41/ds4_model.cu:456-470`）。

この変数専用のログや警告はありません。direct read と buffered fallback がともに失敗した場合には読み込み失敗として上位へ伝わります。たとえば embedding の読み込みでは `embed.weight: read failed` が返されます（`src/dsv41/ds4_model.cu:2800-2826`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:273`。
- 唯一の環境読み取りと Windows 分割実装: `src/dsv41/ds4_os.hpp:113-153`。リポジトリ全体の完全一致検索でも環境から読む実装はこの1か所でした。
- 読み込み handle と direct read の利用: `src/dsv41/ds4_model.cu:386-404,455-497`; `src/dsv41/ds4_pool.hpp:220-241`。
- エンジンのビルド条件: `CMakeLists.txt:906-920`。`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。
