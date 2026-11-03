# `DS4_RECENT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 (DS4) モデルの expert cache に、最近 CPU lane で使われた expert の複製を置く VRAM slot 数を指定します。通常の VRAM expert と swap 用の spare slot とは別に枠を確保し、CPU lane で繰り返し選ばれた expert を非同期にコピーして次の window 以降で使えるようにします。`src/dsv41/ds4_model.cu:908-920,1577-1603,9079-9155`。

## 値と判定

環境値は共通 helper `env_f()` で `std::atof()` に渡し、`float` に変換後 `int` にキャストし、`std::max(0, ...)` で負数を 0 にします。文字列全体の検証や明示的な上限 clamp はありません。`src/dsv41/ds4_model.cu:1352,1582,2800`。

| 状態・値 | 判定 |
|---|---|
| unset | Impl 構築時の初期値は 0。モデル load 時は後述の条件をすべて満たす場合だけ既定値 32、それ以外は 0。 |
| 空文字・数値として読めない文字列 | `atof()` の結果は 0 となり、slot 数 0。 |
| 数値文字列 | `atof()` の結果を `int` に切り捨ててから負値を 0 にする。小数部は切り捨て。 |
| 負数 | キャスト後に 0。 |
| 数値の後ろに文字が続く値 | `atof()` が数値として読める先頭部分を使う（例: `3xyz` は 3）。 |
| `NaN` / `Inf` や `int` の範囲を超える値 | 入力全体の検証・範囲 clamp はなく、float から int への変換結果をこの実装から安全な slot 数として保証できない。 |

構築時に一度読み、load の chunk と streaming 設定が確定した後にもう一度読み直して値を上書きします。したがって実際の slot 配置には load 時の読み取りが使われ、その後の変更は反映されません。CLI 引数による `DS4_RECENT` の上書き箇所は見つかりませんでした。`src/dsv41/ds4_model.cu:1582,2793-2802`。

## 有効になる条件

unset 時の load 既定値 32 は、次をすべて満たす場合です。

- prompt が chunk prefill で `chunk > 0`。
- pack が GGUF (`pk.gguf`)。
- `ln_land` が有効。
- `DS4_STREAM`（未設定なら `STRATA_DS4_STREAM`）が off でない。

それ以外の unset は 0 です。`DS4_STREAM` が未設定、または `atoi()` が 0 となる値なら lane は off と判定されます。`DS4_LAND` が未設定の場合、`ln_land` は one-GPU path の判定に従います。自動 path は HIP 以外で NVIDIA の単独 discrete GPU / 単独 group の場合に候補となり、lane が off、または lane calibration が off なら無効です。`DS4_LAND` を明示すると `env_tri()` の判定がこの既定を上書きします。`src/dsv41/ds4_model.cu:2793-2800,6090-6139,9711-9719`。

正の値を明示すれば上記の unset 既定条件に関係なく候補数になりますが、実際に layer の slot になるのは expert cache が有効で、その layer の expert が VRAM に一部だけ収まり (`n_slots >= 2 && n_slots < n_exp`)、MTP layer ではなく、指定数に加えて通常用 slot と swap 用 spare slot を各 1 個残せる場合です。満たさない layer ではその layer の recent slot 数を 0 にします。指定数を利用可能な範囲へ縮める clamp はなく、条件に合わなければ枠を作りません。`src/dsv41/ds4_model.cu:5553-5564`。

自動 streaming path の有効条件は NVIDIA などに限られますが、slot の確保自体は明示した `DS4_RECENT` と上記 layer 条件で決まります。streamed expert を recent slot へ直接着地させる処理はさらに `DS4_LAND` 相当の `ln_land`、単一 member layer (`nm == 1`)、対象 expert が swap 中でないことを要求します。`src/dsv41/ds4_model.cu:6103-6139,9985-10011`。

## 実行時の詳細

各 cache tick で layer ごとの CPU lane 使用 expert を履歴に追加し、直近 `DS4_RECENT_WIN` tick のうち `DS4_RECENT_NEED` 回以上使われた未常駐 expert を fill 候補にします。既定は窓 8、必要回数 2、tick あたりの新規 fill 上限 `DS4_RECENT_FILLS=2` です。いずれも 1 以上に丸められます。空き slot を優先し、なければ fill / landing 中でない slot のうち最も古いものを再利用します。`src/dsv41/ds4_model.cu:1577-1585,8802-8809,9110-9155`。

fill thread は tick の table 更新後に別 stream で expert をコピーします。完了した slot は後続 tick で expert table に反映されます。streamed expert の landing 先になった場合は window 後の map で反映し、置き換えられた expert の table entry は無効化されます。`src/dsv41/ds4_model.cu:8855-8890,8892-8944,8970-9011,9985-10011`。

### 観測できる結果

- コピー開始に失敗すると stderr に `ds4: recent-slot fill failed, slot left unmapped: ...` を出し、その slot は unmapped のままです。`src/dsv41/ds4_model.cu:8903-8925`。
- prompt / picture 用に VRAM tail を貸し出す前の fill 待ちは最大 5000 ms です。timeout 時は一度だけ `ds4: recent slots: ... fills still running ... before a prompt - the prompt goes on without waiting for them` を stderr に出し、待たずに続行します。`src/dsv41/ds4_model.cu:9050-9077,12621-12630,12657-12673`。
- `DS4_RECENT_STATS` が unset でなければ（空文字も含む）、recent slot の tick が 1 回以上あった場合に終了処理で tick 数、tick あたり時間、fill 開始数・完了数、streamed expert landing 数の平均を stderr に出します。`src/dsv41/ds4_model.cu:1924-1928`。

`docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。性能・正確性への効果はこの文書では主張しません。

## 根拠

- `src/dsv41/ds4_model.cu:1352,1582,2793-2802` — helper の変換、構築時と load 時の読み取り、unset 時の既定値。
- `src/dsv41/ds4_model.cu:6090-6139,9711-9719` — one-GPU / stream / land の既定と明示設定。
- `src/dsv41/ds4_model.cu:5553-5564,5645-5662` — layer ごとの slot 適用条件と slot/event 初期化。
- `src/dsv41/ds4_model.cu:8802-8809,9079-9155` — cache tick、履歴条件、非同期 fill の開始。
- `src/dsv41/ds4_model.cu:8855-8944,8970-9011,9985-10011` — copy 完了、table 反映、streaming landing。
- `src/dsv41/ds4_model.cu:8903-8925,9050-9077,1924-1928` — 失敗・待機 timeout・統計ログ。
