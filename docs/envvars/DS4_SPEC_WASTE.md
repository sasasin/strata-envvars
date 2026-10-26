# `DS4_SPEC_WASTE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DSv4.1 の CUDA prompt expert stream で、ルーティング結果が出る前に次の layer の expert を先読みする動作を、過去に先読みした expert の未使用率に応じて止める閾値です。先読み候補の確率を決める `DS4_SPEC_Q` とは別に、先読みを継続するかを制御します。

## 値と判定

値は `std::atof()` で `double` に変換され、既定値は `0.2` です。文字列全体の検証、エラー検出、範囲制限はありません。`atof` が数値として読める先頭部分を変換し、数値として読めない文字列は `0` として扱われます。空文字も `0` になります。

| 設定 | `waste` の値 |
|---|---:|
| unset | `0.2` |
| `0.2`, `0.2suffix` | `0.2` |
| 空文字、数値で始まらない文字列 | `0` |
| 負数、1を超える数 | その数値のまま（clamp なし） |

`flow_spec()` の各呼び出しで、次の条件が成立するときだけ先読み候補を作ります。

```text
it_spec < 2 * ring_n
または
it_spec_unused <= waste * it_spec
```

`it_spec` はその run で先読みキューに積んだ候補数の累計、`it_spec_unused` はそのうち実際には選ばれなかった数の累計です。したがって、最初の `2 * ring_n` 件は未使用率にかかわらず先読みされます。その後は未使用率が `waste` 以下の間だけ続き、超えると後続の先読み候補を作りません。比較は `<=` です。停止後は候補数も未使用数も増えないため、その run の残りでは停止状態が続きます。負の閾値では `it_spec` が `2 * ring_n` 以上になった後に条件を満たさなくなります（その件数に達するだけ候補が存在する場合）。1以上の閾値では未使用率がその値を超えない限り継続します。

## 有効になる条件

この変数が使われるのは `src/dsv41/ds4_model.cu` の CUDA expert flow 経路だけです。モデルロード時に file experts 用の flow が作られ、実行時の chunk が `c.flow` のとき `flow_spec()` が呼ばれます。flow は既定で有効ですが、`DS4_FLOW` が設定されて `atoi` の結果が 0 の場合は無効です。Tensor parallel の各メンバーでは `DS4_FLOW_TP` が非0であることなど、flow の追加条件があります。

flow の作成には、chunked prompt 経路が有効であること、対象層が MXFP4 であること、および各デバイスの配置条件を満たすことが必要です。`DS4_CHUNK_MIN` は chunk の最小長を明示的に上書きできます。これらの条件を満たさず通常の windows 経路を使う場合、この値による先読み判定は行われません。

## 実行時の詳細

`waste` は `flow_spec()` 内の function-local `static const` で、プロセス内の最初の呼び出し時に一度だけ読み取られます。以後プロセス環境を書き換えても再評価されません。`it_spec` と `it_spec_unused` は flow を実行する run の開始時に0へ戻されます。

先読みを許可した場合、実装は CPU lane の expert について profile から選択確率を求め、`DS4_SPEC_Q` 以上の確率で1回以上選ばれる見込みの候補を、確率順に最大 `S + ring_n` 件キューへ積みます。ここで `S` は staging slot 数です。実際に routing された候補は通常の処理に使われ、候補のうち選ばれなかったものは `it_spec_unused` に加算されます。先読みが止まった後も、routing が選んだ残りの expert は `flow_rest()` から通常どおり読み込みます。

`o.verbose` または `DS4_FLOW_STATS` が設定されていると、stderr の `ds4 prompt stream` 統計行に `likely ones queued early` と `of them unpicked` の累計が表示されます。`DS4_FLOW_STATS` はここでは値の内容でなく設定有無を見ます。

## 文書・測定との照合

`docs/DETAILS.md` には `DS4_SPEC_WASTE` の値や判定式の説明を確認できませんでした。`ds4_model.cu` のコメントには特定環境での未使用件数や速度例がありますが、条件・測定手順が十分に記されていないため、一般的な性能値としては扱っていません。

## 根拠

- `src/dsv41/ds4_model.cu:597,7628-7635` — カウンターの定義と run ごとの初期化。
- `src/dsv41/ds4_model.cu:3326-3375` — 候補の確率判定、`DS4_SPEC_WASTE` の読み取り、先読み件数の累積。
- `src/dsv41/ds4_model.cu:3377-3389,3544-3547` — 先読み候補の未使用判定と、次 layer の先読み呼び出し。
- `src/dsv41/ds4_model.cu:2704-2737` — flow の既定、`DS4_FLOW` / `DS4_FLOW_TP`、MXFP4 条件と flow 初期化。
- `src/dsv41/ds4_model.cu:8397-8405` — verbose / `DS4_FLOW_STATS` 時の統計ログ。
