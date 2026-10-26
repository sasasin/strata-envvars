# `DS4_STORE_FLOOR_GB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4 の RAM store が新しいメモリ chunk を commit するとき、空けておく RAM の下限を指定します。デフォルトは 8 GiB です。store の上限容量を決める変数ではなく、RAM の空き容量がこの下限を保てない場合に store の拡張を止めます。

## 値と判定

`init_store()` が環境変数の有無を調べ、設定されていれば `std::atof()` で値を `double` にし、`size_t` に変換してから 30 bit 左シフトします。未設定の場合は `8.0` を使います。

| 環境変数 | `cfg.floor_bytes` |
|---|---:|
| 未設定 | `8 << 30` bytes（8 GiB） |
| `0`、空文字、数値に変換できない文字列 | 0 bytes |
| `1.9` | 1 GiB（`size_t` 化で小数部を落としてからシフト） |
| `12.5GiB` | 12 GiB（数値の後ろは `atof` が解釈せず、変換可能な数値 prefix を使う） |

`atof` による変換なので、整数専用ではなく小数や指数表記も数値 prefix として受け付けます。空白の扱い、数値 prefix がない場合の 0 への変換も `atof` に従います。値の範囲検証や clamp はありません。負数、NaN、`size_t` の範囲を超える値を `size_t` に変換した場合の結果は、C++ の浮動小数点から整数への変換規則上、通常の設定値として保証できません。

## 有効になる条件

この値は DS4 モデルのロード中に `init_store()` で `ExpertStore::Cfg` に設定されます。RAM store 自体は、store 容量 `gb` が正、レイヤーが空でない、先頭レイヤーの形式が MXFP4、かつ expert がファイルから読む構成である場合だけ初期化されます。容量は `--ssd-cache` または `DS4_STORE_GB` などで別途指定されます。これらの条件を満たさない場合、この変数の値は store の動作に影響しません。

## 実行時の詳細

環境変数はモデルロード時の `init_store()` で読み取られます。store は拡張時に chunk の byte 数を計算し、現在の RAM 空き容量 `avail` が取得できるとき、`avail < chunk_bytes + floor_bytes` なら chunk の commit を行わず `grow()` を失敗させます。空き容量が不明値 (`~uint64_t{0}`) のときはこの床チェックをスキップします。

拡張できない場合、store は既存の free slot または eviction 可能な slot を使おうとします。したがって床値は store の既存領域を即時解放する設定ではなく、追加 chunk の commit を制限する値です。この環境変数専用のログやエラー出力はありません。起動後に環境を変更しても、初期化済み `cfg.floor_bytes` には反映されません。

`docs/DETAILS.md` にはこの環境変数の個別説明や測定値を確認できませんでした。

## 根拠

- `src/dsv41/ds4_model.cu:2821-2822` — モデルロード中に store 初期化と preload を呼び出す。
- `src/dsv41/ds4_model.cu:4633-4636` — RAM store の初期化条件。
- `src/dsv41/ds4_model.cu:4657-4661` — `DS4_STORE_FLOOR_GB` の読み取り、既定値 8.0、変換、byte 数への設定。
- `src/dsv41/ds4_store.hpp:58-70` — `Cfg::floor_bytes` の用途コメントと既定値。
- `src/dsv41/ds4_store.hpp:480-493` — 空き RAM と床値の比較、chunk commit。
- `src/dsv41/ds4_store.hpp:495-524` — 拡張失敗後の slot 再利用・eviction 探索。
