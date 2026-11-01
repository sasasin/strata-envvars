# `DS4_LA_THREADS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 の Metal 実装で、router lookahead が予測した CPU 側 expert のファイル範囲を `os::prefetch` する detached helper thread の数を指定します。expert の選択数や計算結果はこの変数では変わりません。

このコードは `STRATA_METAL` のときだけコンパイルされます。また `strata-dsv41` 自体も `STRATA_BUILD_DSV41` が有効な場合だけ CMake のターゲットに追加され、同オプションは既定で OFF です（`src/dsv41/ds4_model.cu:6544-6545`, `CMakeLists.txt:906-920`）。

## 値と判定

`LaPool` の初回生成時に `std::getenv` で設定有無を調べ、設定されていれば `std::atoi`、未設定なら `3` を使います。文字列全体の検証や範囲 clamp はありません。

| 値 | `atoi` の結果と動作 |
|---|---|
| 未設定 | 既定値 `3`。3 worker を生成 |
| 空文字 | `0`。worker は生成されない |
| 整数として認識できる先頭部分がある文字列 | `atoi` が先頭の整数を変換し、後続文字を無視。例: `4xyz` は `4` worker、`-2` は `-2` |
| 数字に変換できない文字列 | `0`。worker は生成されない |
| 正の整数 `n` | `n` worker を生成。上限チェックなし |
| `0` または負数 | ループ条件 `i < nth` が成立せず、worker は生成されない |
| `int` に表せない数値 | `atoi` の結果は規格上未定義。Strata による検証・fallback なし |

先頭の空白と符号は `atoi` の整数変換規則に従います。正の値についても上限や clamp はありません。`std::thread` 作成時の失敗をこの constructor 内で処理するコードはありません（`src/dsv41/ds4_model.cu:6555-6583`）。

## 有効になる条件

- `STRATA_METAL` ビルドであること。CUDA/HIP 側ではこの lookahead pool と環境変数読み取りはコンパイル対象外です（`src/dsv41/ds4_model.cu:6544-6545,10527-10529`）。
- `strata-dsv41` がビルドされていること（`CMakeLists.txt:906-920`）。
- forward が async 経路を通らず host-routed path に到達すること。async 経路はその場で return するため、後段の `lookahead_prefetch` 呼び出しに進みません（`src/dsv41/ds4_model.cu:10301-10412`）。Metal では `DS4_ASYNC` が未設定なら `sync_decode` は true です。設定がある場合は false となり、window サイズ等に応じて async 経路になります（`src/dsv41/ds4_model.cu:1126-1131,9565-9569`）。
- その host-routed forward が `T == 1` であること。さらに `lookahead_prefetch` は現在層の `l.nm == 1` を要求します（`src/dsv41/ds4_model.cu:6592-6593,10527-10529`）。
- 実際に予測 expert の prefetch を enqueue するには、別変数 `DS4_LOOKAHEAD` による lookahead depth が正で、次層の条件を満たす必要があります。depth は未設定なら `0`、設定値は `atoi` 後に最大 `2` へ clamp されます。次層が単一 GPU、MXFP4、router bias と gate weights を持つ条件を満たさないと予測を止めます（`src/dsv41/ds4_model.cu:6550-6554,10432-10447`）。

`DS4_LA_THREADS` 自体には CLI 引数や別環境変数による上書き経路は見つかりません。`DS4_LA_MAX` は各予測層から enqueue する CPU expert 数を制限しますが、worker 数は変えません（`src/dsv41/ds4_model.cu:6612-6623`）。

## 実行時の詳細

`lookahead_prefetch` の初回呼び出し時に関数内 static の `LaPool*` を生成し、その constructor が `DS4_LA_THREADS` を評価します。値は pool の生存中に再評価されず、後から環境を変えても worker 数は変わりません。pool は pointer として保持され、各 worker は detach されて無限ループで待機します（`src/dsv41/ds4_model.cu:6555-6583,6592-6599`）。

予測が有効な場合、次層以降で VRAM slot にない予測 expert の各3 matrix の範囲を queue に追加します。worker は queue から範囲を取り、`mincore` で resident 状態を確認し、cold と判定した範囲を `os::prefetch` に渡します。これは Strata が行う先読み I/O 要求です（`src/dsv41/ds4_model.cu:6572-6581,6612-6623`）。

worker 数を `0` 以下にしても queue への追加は無効になりません。`DS4_LOOKAHEAD` とモデル条件が満たされていれば enqueue は続きますが、queue を処理する worker はおらず、queue を捨てる処理も worker loop 内にしかありません（`src/dsv41/ds4_model.cu:6561-6571,6610-6623`）。したがって `DS4_LA_THREADS=0` は lookahead の無効化設定ではありません。lookahead を止める条件は `DS4_LOOKAHEAD` 側にあります。

この変数専用の起動ログや値の警告はありません。`DS4_CPU_LOG` が設定されている場合に限り、終了時に `lookahead: %ld of %ld CPU-lane experts were guessed; %ld matrices queued` を stderr に出す登録があります。これは guess / enqueue 数であり worker 数は表示しません（`src/dsv41/ds4_model.cu:6600-6604`; `ds4_dbg` は Metal で環境変数の設定有無を確認します: `src/dsv41/ds4_launch.h:30-36`）。

## 根拠

- 候補一覧にも名前があります: `docs/envvars/000_envvers.md:219`。Strata ソースの完全一致参照は `src/dsv41/ds4_model.cu:6560` の一箇所で、そこで実際に環境から読み取られています。
- 値の変換、既定値、thread 生成: `src/dsv41/ds4_model.cu:6555-6583`。
- lookahead の値判定と GPU 側予測条件: `src/dsv41/ds4_model.cu:6550-6554,10432-10447`。
- host-routed path からの呼び出しと async 経路: `src/dsv41/ds4_model.cu:10301-10417,10527-10529`。
- `strata-dsv41` の opt-in build target: `CMakeLists.txt:906-920`。
