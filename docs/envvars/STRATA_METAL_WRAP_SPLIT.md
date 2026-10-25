# `STRATA_METAL_WRAP_SPLIT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal の `Context::wrap(ptr, bytes, max_span)` が、デバイスの `maxBufferLength` を超える領域を複数の重なり合う `MTLBuffer` に分割して包む動作を止めるための変数です。主な利用箇所は、Metal window engine がメモリマップしたモデル shard 全体を包む経路です。

## 値と判定

`Context::wrap` の呼び出しごとに `std::getenv` で値を読み、設定値全体を `std::string` として `"0"` と比較します。数値変換や真偽値 parse はありません。

| 値 | `bytes <= maxlen` | `bytes > maxlen` |
|---|---|---|
| 未設定 | 通常の単一 buffer wrap | 重なりのある複数 buffer に分割 |
| 空文字 | 通常の単一 buffer wrap | 重なりのある複数 buffer に分割 |
| 正確に `0` | 通常の単一 buffer wrap | 分割せず、通常の単一 buffer wrap を試す |
| その他（例: `1`, `00`, `false`, `0 `） | 通常の単一 buffer wrap | 重なりのある複数 buffer に分割 |

大文字小文字や空白は正規化されません。値は static cache されず、各呼び出しで確認されます。ただし、通常の Metal window 初期化では当該 wrap を一度呼ぶため、その呼び出し後に環境を変更しても既に作成した buffer には反映されません。

## 有効になる条件

- Metal backend の実装が対象です。
- `bytes <= floor(maxBufferLength / 16384) * 16384` の領域は常に単一 buffer 経路となり、この変数による差はありません。
- 主な本番呼び出し元は `metal/src/engine/window.cpp` のモデル shard wrap です。SSD streaming が選択された場合は、この shard 全体を包む分岐ではなく `ExpertStream` を開くため、この呼び出しの変数判定には到達しません。
- 分割時は最大 buffer 長を 16 KiB 境界に切り下げ、`max_span` を 16 KiB 単位に切り上げます。分割幅は `maxlen - span` です。`span >= maxlen / 2` のときは `mtl: wrap ...: a tensor ... does not fit the chunks` を stderr に出して終了コード 4 で終了します。
- `STRATA_METAL_WRAP_SPLIT=0` で上限超過を単一 buffer として包もうとした際に `newBufferWithBytesNoCopy` が失敗すると、`mtl: wrap %zu failed` を stderr に出して終了コード 4 で終了します。Metal API 側の制約や失敗理由の詳細はここでは説明しません。

## 実行時の詳細

Metal window engine は streaming を使わない場合、モデル shard の tensor 最大サイズと、各層の routed expert の連続範囲を走査し、その最大値を `max_span` として求めます。その後 shard 全体を `Context::wrap` に渡します。shard が `maxBufferLength` を超えていて分割が許可されると、各 chunk の開始間隔を `maxlen - span` として、chunk 境界をまたぐ最大 `span` のアクセス範囲が少なくとも一つの buffer に収まるよう、重複部分を設けます。成功時は分割した総バイト数、buffer 数、上限、重複幅を stderr に記録します。

この環境変数は engine 起動時に子プロセスへ転送される設定ではなく、Metal runtime 内で直接読み取られます。CLI や設定ファイルによる上書き処理は見つかりません。

## 根拠

- `metal/src/mtl_rt.mm:193-223` — 判定、16 KiB 境界の丸め、単一 buffer / 分割経路、分割条件、ログと失敗時処理。
- `metal/src/mtl_rt.mm:225-237` — 通常の単一 buffer wrap と失敗時のログ・終了。
- `metal/src/engine/window.cpp:433-456` — streaming でない場合の shard 範囲計算と `Context::wrap` 呼び出し。
- `metal/src/engine/stream.cpp:417-459` — streaming arena は上限内の複数領域を作り、2 引数版の wrap を使うこと。
- `metal/src/mtl_rt.h:18-25,94-98` — Buffer の chunk 情報と wrap API の説明。
