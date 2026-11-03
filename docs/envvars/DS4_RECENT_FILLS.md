# `DS4_RECENT_FILLS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 engine (`strata-dsv41`) の expert cache にある recent slots へ、各 tick で新たにコピーを始める CPU-lane expert の最大数を指定します。値はコピー候補を選ぶ上限であり、recent slots 自体を有効化したり、層ごとの slot 数を決めたりはしません。recent slots が無効なら、この値は使われません。

この実装は `src/dsv41/ds4_model.cu` にあり、CMake の `STRATA_BUILD_DSV41` が有効なときに `strata-dsv41` へ組み込まれます。この build option は既定 OFF です。HIP gfx906 ではこの target を作らない条件になっています (`CMakeLists.txt:931-945`)。

## 値と判定

`env_f` は変数が未設定なら既定値を返し、設定されていれば `std::atof` で `float` に変換します。その後 `int` にキャストし、`std::max(1, ...)` で下限を 1 にします (`src/dsv41/ds4_model.cu:1352,1583`)。

| 入力 | `recent_fills` |
|---|---:|
| 未設定 | 2 |
| 空文字 | 1 (`atof("")` が 0 相当となり、下限 1 を適用) |
| 有限な数値文字列 | `int` への切り捨て後、最低 1。例: `4` → 4、`2.9` → 2、`0` / `-3` → 1 |
| 数値として読めない文字列 | `atof` の 0 相当から 1 |

文字列全体の妥当性検査や明示的なエラー処理はありません。`atof` が読める数値の後ろに文字があっても、コードは変換結果をそのまま使用します。`int` の表現範囲を外れる値や NaN などを `int` に変換するケースの結果は、この実装から保証できません。

## 有効になる条件

`DS4_RECENT_FILLS` は単独では機能を有効にしません。まず `DS4_RECENT` により `recent_n > 0` となり、層に recent slots が割り当てられる必要があります。`DS4_RECENT` が未設定なら、モデル準備時に chunked prompt、GGUF pack、`ln_land` が有効、stream lane が無効でないことを条件として既定値 32、それ以外は 0 が選ばれます。`ln_land` は通常 one-GPU path に従いますが、`DS4_LAND` で明示的に上書きできます。`DS4_RECENT` が設定されていれば、その値がこの自動既定値に優先します (`src/dsv41/ds4_model.cu:2793-2800,6103-6138`)。

層ごとの recent slots は、CLI の `--no-expert-cache` が指定されておらず、層に少なくとも 2 個かつ全 expert 未満の VRAM slot がある場合に限り検討されます。さらに `recent_n > 0`、非 MTP 層で、recent slots と cache 用 spare slot を確保しても通常の VRAM expert slot が 1 個以上残る場合に割り当てられます (`src/dsv41/ds4_main.cpp:2535`; `src/dsv41/ds4_model.cu:5553-5564`)。したがって VRAM 容量やモデルの層構成により、一部または全層で値が使われないことがあります。

## 実行時の詳細

`recent_fills` は `Model::Impl` の初期化時に一度読み取られ、`const` メンバーに保存されます。実行中に環境変数を変えても再評価されません (`src/dsv41/ds4_model.cu:1582-1585`)。別変数の `DS4_RECENT` はモデル準備時に再評価され、自動で recent slots を使うか、明示値で上書きするかを決めます (`src/dsv41/ds4_model.cu:2797-2800`)。

expert-cache の tick は recent-slot の更新処理を呼びます (`src/dsv41/ds4_model.cu:8802-8808`)。`rc_tick` は `recent_n <= 0` または recent slots を持つ層がない場合に戻ります。各対象層では直近 tick 群で `DS4_RECENT_NEED` 回以上 CPU lane に選ばれた未常駐 expert を候補とし、空きまたは最も古い利用 slot を選びます。その tick にコピー開始できる候補は `recent_fills` 件までです。`DS4_RECENT_NEED` と `DS4_RECENT_WIN` の既定値はそれぞれ 2 と 8 です (`src/dsv41/ds4_model.cu:1584-1585,9079-9083,9112-9155`)。この上限は層ごとに適用され、コピー可能な slot や条件を満たす expert が少なければ実際の件数も少なくなります。queue に入ったコピーを別 thread が発行し、完了後の tick で slot を table に反映します (`src/dsv41/ds4_model.cu:8883-8890,8892-8944,9005-9011`)。

コピー発行に失敗すると stderr に `ds4: recent-slot fill failed, slot left unmapped: ...` が出て、その slot は対応する expert に割り当てられません (`src/dsv41/ds4_model.cu:8903-8925`)。`DS4_RECENT_STATS` が設定され、tick があった場合は終了時に tick あたりの開始数・完了数・streamed expert landing 数などが stderr に出ます。この統計の有無は fill 上限を変えません (`src/dsv41/ds4_model.cu:1924-1928`)。上限値自体に対する警告や終了経路はありません。

## 根拠

- 対象名の実読み取りは `src/dsv41/ds4_model.cu:1583` の 1 箇所です。同ファイルの `env_f` 定義は `src/dsv41/ds4_model.cu:1352`。他の対象名参照 `src/dsv41/ds4_model.cu:1577` は説明コメントです。
- 自動有効条件と `DS4_RECENT` による上書き: `src/dsv41/ds4_model.cu:2793-2800`。
- expert cache / 層 / VRAM slot の割当条件: `src/dsv41/ds4_model.cu:5553-5564`。
- recent-fill の履歴・候補・上限処理: `src/dsv41/ds4_model.cu:9112-9155`。
- build target の条件: `CMakeLists.txt:931-945`。
