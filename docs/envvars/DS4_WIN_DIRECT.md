# `DS4_WIN_DIRECT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Windows 上の DS4 エンジンが GGUF ファイル用に開く、非バッファー読み取りハンドルを無効化します。無効にすると、expert の読み込みは buffered read 経路を使います。Linux ではこの環境変数を読みません。

## 値と判定

Windows の `open_direct()` が初回に `std::getenv()` で読み、その結果を関数内 `static const bool` に保存します。値の文字列全体ではなく `std::atoi()` の結果を判定します。

| 値 | Windows での判定 |
|---|---|
| 未設定 | 有効（既定） |
| `0`、`00`、`0junk`、数値変換できない文字列、空文字 | 無効（`atoi` が 0） |
| `1`、`-1`、`2`、`1junk` | 有効（`atoi` が 0 以外） |

`atoi` が認識する先頭の空白と符号は数値変換に従います。数値としての範囲外の文字列は C ライブラリの `atoi` の動作に依存し、Strata 側で別途検証や clamp はしません。Linux の `open_direct()` は `O_DIRECT` で開き、`DS4_WIN_DIRECT` を参照しません。

## 有効になる条件

- DS4 エンジンが Windows で動作し、読み込む pack の `format` が `gguf` の場合に限り、この判定が GGUF shard ごとの direct handle 作成に使われます。
- EXL3 pack では shard 用 `open_direct()` を呼ばないため、この変数の判定は使われません。
- `DS4_WIN_DIRECT` を `0` にして direct handle を作らない場合も、ファイルの読み込み自体は失敗扱いになりません。通常の buffered read 用 handle は別途開かれます。
- 値が有効でも、OS が direct handle を開けない場合、または個別の direct read が失敗した場合は buffered read に fallback します。

## 実行時の詳細

GGUF pack のロード時、各 shard を read-only に開いて memory map した後、`open_direct()` と並列 read 用 `open_par()` を呼びます。Windows でこの変数が無効なら `open_direct()` は `kBadFd` を返します。expert の読み込み job は direct handle があり、対象範囲がすでに page cache に resident でなく、かつ direct read に成功したときだけ direct read を採用します。それ以外は並列 buffered read を試します。

`open_direct()` 内の `static` 判定はプロセス内で最初に呼んだときに一度だけ行われます。その後に環境変数を変更しても再評価されません。DS4 の RAM store の起動ログは direct handle が全 shard で作れた場合に `unbuffered reads`、そうでなければ `BUFFERED (no direct handle)` と表示します。この表示は各読み込み job が実際に direct read を使ったことまでは示しません。

`docs/DETAILS.md` にこの環境変数の個別説明や測定値は見つかりませんでした。

## 根拠

- `src/dsv41/ds4_os.hpp:65-93`: platform 分岐、Windows での `atoi` 判定、`CreateFileW` の direct flags、Linux での `O_DIRECT`。
- `src/dsv41/ds4_model.cu:314-331`: shard を開く処理、GGUF 条件、mapping 後の direct / parallel handle 作成。
- `src/dsv41/ds4_pool.hpp:201-214`: resident 範囲を避けた direct read と buffered fallback。
- `src/dsv41/ds4_model.cu:4708-4723`: RAM store 起動ログの判定と文言。
