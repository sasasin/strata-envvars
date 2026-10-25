# `--no-expert-cache`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業ツリーは `git status --short --branch` で `main...origin/main` と表示され、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（トップレベル） |
| オプション | `--no-expert-cache` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

expert の VRAM/CPU 間の動的な入れ替えを無効にします。既定では有効です。これは DeepSeek-V4.1 用の独立 engine CLI のオプションです。`strata-dsv41` は `STRATA_BUILD_DSV41=ON` で生成されます（`CMakeLists.txt:797-811`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1,2,3 --no-expert-cache
```

`--ids` を使う通常の推論例です。サーバー起動など `Model` を読み込む他の実行モードにも同じ engine 設定が適用されます。

## 値と既定値

- 値や `=` 形式は不要です。parser がこの引数を見つけると `Options::expert_cache` を `false` にします。値の検証や範囲検査はありません（`src/dsv41/ds4_main.cpp:1200-1208,1223`）。
- 指定しない場合は `Options::expert_cache = true` です（`src/dsv41/ds4_model.hpp:32-33`）。複数回指定しても同じ boolean を `false` にするだけです。
- フラグに値を付ける構文はありません。引数リストに別の未知オプションが現れた場合、`unknown option` と usage を stderr に出し、終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1269-1272`）。

## 実行時の動作

- expert 配置の初期化では、profile のヒット数が多い expert から VRAM slot に割り当てます。キャッシュが有効で、VRAM に収まらない expert があり、slot が2つ以上ある層では、入れ替え用に1 slot を空けます。このフラグを指定するとその予約を行わず、割り当て可能な slot 数まで profile 順の expert を初期配置します（`src/dsv41/ds4_model.cu:3880-3897`）。profile の既定ファイルは `<pack>/expert-profile.bin` で、`--expert-profile none` なら無効です（`src/dsv41/ds4_main.cpp:1286-1287`）。
- 動的な入れ替え用の host buffer、CUDA stream、cache worker thread は作成されません（`src/dsv41/ds4_model.cu:2750-2765`）。expert cache の定期更新と prompt 後の cache settle も早期 return します（`src/dsv41/ds4_model.cu:5907-5914,5967-5969`）。そのため、初期配置されなかった expert は動的に VRAM へ移りません。
- `STRATA_DS4_RAM_TIER` による RAM tier が有効な構成では、起動時に profile 順の CPU-lane expert を RAM に先読みする処理自体はありますが、このフラグがあると RAM tier の入れ替え worker は開始されません（`src/dsv41/ds4_model.cu:4082-4119`）。
- SSD store は別系統です。`init_store()` はこの boolean を条件にせず構成され、expert の読み出し時には store 内のデータも検索します。したがって、このフラグは `--ssd-cache 0` と同義ではありません（`src/dsv41/ds4_model.cu:1689-1698,4457-4472`）。
- `--pack-info` は pack の情報を表示して `Model::load()` より前に終了するため、このフラグによる expert 配置・cache の動作は発生しません（`src/dsv41/ds4_main.cpp:1276-1280,1289-1296`）。

## 適用条件と副作用

`Model::load()` を通る推論・serve 等に適用されます。動的入れ替えを止める一方、VRAM に部分配置する層では入れ替え用の空き slot を作らず、そのぶん初期配置 expert 数が増える場合があります。どちらが速いか、また全モデル形式での性能差はこのソース調査からは判断できません。

起動時の GPU 割り当て、profile 読み込み、expert の初期読み込みは引き続き行われます。このフラグ専用の警告や標準出力は確認できません。通常のモデル読み込みに失敗した場合は `maya-ds4: <理由>` を stderr に出して終了コード 1 となります（`src/dsv41/ds4_main.cpp:1289-1294`）。

## 出力とエラー

- 値を必要としないため、オプション単独で「値が不足」エラーにはなりません。
- オプション名自体の parser validation はなく、未知の引数は stderr に usage とエラーを出して終了コード 2 です（`src/dsv41/ds4_main.cpp:1269-1272`）。
- cache 無効化に固有のエラー経路は確認できません。GPU/モデルのロード失敗は一般の `Model::load()` エラーとして stderr に出力され、終了コード 1 です（`src/dsv41/ds4_main.cpp:1289-1294`）。

## 根拠

- parser と usage: `src/dsv41/ds4_main.cpp:85-93,1200-1223`
- 既定値: `src/dsv41/ds4_model.hpp:25-40`
- profile 順の初期配置と入れ替え slot: `src/dsv41/ds4_model.cu:3880-3905`
- worker の作成、RAM tier の worker、更新・settle の条件: `src/dsv41/ds4_model.cu:2750-2765,4082-4119,5907-5914,5967-5969`
- SSD store の初期化と expert 読み出し: `src/dsv41/ds4_model.cu:1689-1698,4457-4472`
- CLI の未知オプション処理、早期終了とモデル読み込みエラー: `src/dsv41/ds4_main.cpp:1269-1296`

同一 revision の既存 `strata-dsv41 --help` は実行していません。値の規則と動作は parser および使用箇所を確認して記載しました。Release 配布物や各 GPU/backend 上での実行結果・性能は調査していません。
