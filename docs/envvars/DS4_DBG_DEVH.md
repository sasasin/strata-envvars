# `DS4_DBG_DEVH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの確認時点の状態は `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

DeepSeek-V4.1 エンジンの Metal ビルドで、モデル実行用の GPU バッファ `d.h` と `d.h2` の確保が成功したとき、デバイス ID と両ポインターを stderr に出す診断スイッチである。計算やバッファ選択を切り替える処理ではなく、診断行の出力だけを制御する。

## 値と判定

`ds4_dbg()` は環境変数の値を解釈せず、`std::getenv(name) != nullptr` だけで判定する。したがって値が空文字でも設定されていれば有効であり、`1` など特定の値は要求されない。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む任意の設定値 | 有効 |

無効値の parse、数値変換、範囲、fallback はない。CLI 引数や別環境変数との優先順位もない。

## 有効になる条件

- `STRATA_METAL` が定義されたビルドであること。Metal 以外では `ds4_dbg(const char*)` が `constexpr false` を返すため、この環境変数を読み取らず、診断行も出ない。
- `strata-dsv41` のモデル初期化で、対象デバイスの一連の `dalloc` がすべて成功し、`ok` が真であること。

`strata-dsv41` の CMake ターゲット自体は `STRATA_BUILD_DSV41` が既定 OFF であり、別実行ファイルとして追加される。Metal ビルド条件の詳細は本調査対象の実装箇所とビルド設定だけでは確定できないため、Metal 以外の backend で値を設定しても効果がない、というソース上の条件を記す。

## 実行時の詳細

モデル初期化中、デバイスごとに `d.h`、`d.h2` を含むバッファ群を確保した直後に `ok && ds4_dbg("DS4_DBG_DEVH")` を評価する。条件成立時の stderr 出力は `DBG devh: id=%d h=%p h2=%p\n` で、`id`、`d.h`、`d.h2` を表示する。`ok` が偽ならこの判定・ログは飛ばされ、後続の `if (!ok) return false;` により関数は失敗を返す。

helper に static cache はなく、呼び出しごとに `getenv` を評価する。対象の呼び出しはデバイス初期化ループ内の一箇所である。CLI 引数による変更、子プロセスへの転送、起動後の環境変更の運用はこの箇所からは確認できない。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal では設定有無を `getenv` で判定し、それ以外では常に false。
- `src/dsv41/ds4_model.cu:2634-2666` — デバイスごとのバッファ確保、`DS4_DBG_DEVH` の判定と stderr 出力、確保失敗時の return。
- `CMakeLists.txt:906-920` — DSV41 は独立した `strata-dsv41` ターゲットで、`STRATA_BUILD_DSV41` は既定 OFF。
- 候補名の全参照検索では、`src/dsv41/ds4_model.cu:2661` の一箇所だけが `DS4_DBG_DEVH` を渡す。動的な名前を受け取る helper は `src/dsv41/ds4_launch.h:34` であり、同 helper の他の呼び出しがこの名前を別の効果へ転送する経路はない。
